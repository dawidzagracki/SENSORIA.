"""Account consents, private data exports and idempotent account closure."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import tempfile
import zipfile
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory, get_session
from sensoria.modules.orders.models import Order, OrderItem, Shipment
from sensoria.modules.vouchers.models import Voucher
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    deleted_email_digest,
    normalize_email,
    require_customer_id,
)
from .clock import utc_now
from .models import (
    AccountActionToken,
    AccountPrivacyJob,
    AccountSession,
    AuthEmailJob,
    ConsentTextVersion,
    Customer,
    CustomerAddress,
    CustomerBillingProfile,
    CustomerConsent,
    DeletedEmailSuppression,
    LoginLink,
)

router = APIRouter(prefix="/privacy", tags=["account-privacy"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, Authorization",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}
CONSENT_COPY: dict[str, tuple[str, str]] = {
    "new_materials": (
        "v1",
        (
            "Wiadomości o nowych materiałach. Raz w miesiącu, bez natrętnych przypomnień. "
            "Wypiszesz się jednym kliknięciem."
        ),
    ),
    "voucher_reminders": (
        "v1",
        (
            "Przypomnienia o voucherach. Przypomnimy przed terminem zgodnie z aktualnymi "
            "progami skonfigurowanymi w sklepie."
        ),
    ),
    "review_requests": (
        "v1",
        "Prośby o opinię. Zapytamy o zdanie po zakupie. Możesz to wyłączyć.",
    ),
}
EXPORT_TTL = timedelta(minutes=15)
EXPORT_COOLDOWN = timedelta(hours=24)
DELETE_REAUTH = timedelta(minutes=10)
PRIVACY_BATCH_SIZE = 10
logger = logging.getLogger("sensoria.accounts.privacy")


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: StrictBool


class DeleteAccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


def _audit(customer_id: UUID, action: str, entity_id: UUID, payload: dict[str, Any]) -> AuditLog:
    return AuditLog(
        actor_type=ActorType.CUSTOMER,
        actor_id=customer_id,
        entity_type="customer_privacy",
        entity_id=entity_id,
        action=action,
        payload={"operation_id": str(entity_id), **payload},
    )


def _ip_hash(request: Request) -> str | None:
    return hashed_client_ip(request)


def hashed_client_ip(request: Request) -> str | None:
    """Return only a keyed digest of the client IP resolved through trusted proxies."""
    from .router import _client_ip

    raw_address = _client_ip(request)
    try:
        address = ipaddress.ip_address(raw_address)
    except ValueError:
        return None
    key = get_settings().SECRET_KEY.get_secret_value().encode()
    return hmac.new(key, b"consent-ip:" + address.packed, hashlib.sha256).hexdigest()


def consent_subject_digest(email: str) -> str:
    """Keep a keyed, non-reversible subject reference after raw email erasure."""
    key = get_settings().SECRET_KEY.get_secret_value().encode()
    normalized = normalize_email(email).encode()
    return hmac.new(key, b"consent-subject:" + normalized, hashlib.sha256).hexdigest()


async def _csrf(request: Request, session: AsyncSession) -> None:
    from .router import _require_csrf

    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    await session.commit()


async def _ensure_consent_text(
    session: AsyncSession, consent_type: str, version: str, text_value: str
) -> ConsentTextVersion:
    row = await session.scalar(
        select(ConsentTextVersion).where(
            ConsentTextVersion.consent_type == consent_type,
            ConsentTextVersion.version == version,
        )
    )
    if row is None:
        row = ConsentTextVersion(consent_type=consent_type, version=version, text=text_value)
        session.add(row)
        await session.flush()
    elif row.text != text_value:
        raise DomainError(
            "CONSENT_TEXT_VERSION_CONFLICT",
            "Nie można zmienić treści przypisanej do wcześniejszej wersji zgody.",
            409,
        )
    return row


async def _current_consent(
    session: AsyncSession,
    consent_type: str,
    *,
    customer_id: UUID | None = None,
    email: str | None = None,
) -> CustomerConsent | None:
    if customer_id is not None:
        predicate = CustomerConsent.customer_id == customer_id
    elif email is not None:
        predicate = CustomerConsent.email == normalize_email(email)
    else:
        return None
    result = await session.scalars(
        select(CustomerConsent)
        .where(CustomerConsent.consent_type == consent_type, predicate)
        .order_by(CustomerConsent.occurred_at.desc(), CustomerConsent.id.desc())
        .limit(1)
    )
    return result.first()


async def has_current_consent(
    session: AsyncSession,
    consent_type: str,
    *,
    customer_id: UUID | None = None,
    email: str | None = None,
) -> bool | None:
    """Shared fail-closed check used both during qualification and before sending."""
    if consent_type not in CONSENT_COPY:
        return None
    latest = await _current_consent(session, consent_type, customer_id=customer_id, email=email)
    return latest.granted if latest is not None else False


def _serialize_consent(
    row: CustomerConsent, text_rows: dict[UUID, ConsentTextVersion]
) -> dict[str, Any]:
    copy = text_rows[row.consent_text_id]
    return {
        "id": str(row.id),
        "type": row.consent_type,
        "granted": row.granted,
        "occurred_at": row.occurred_at.isoformat(),
        "source": row.source,
        "text_version": copy.version,
        "text": copy.text,
    }


@router.get("/consents")
async def list_consents(
    response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, Any]:
    response.headers.update(PRIVATE_HEADERS)
    events = list(
        (
            await session.scalars(
                select(CustomerConsent)
                .where(CustomerConsent.customer_id == customer_id)
                .order_by(CustomerConsent.occurred_at, CustomerConsent.id)
            )
        ).all()
    )
    text_ids = {event.consent_text_id for event in events}
    texts = (
        {
            item.id: item
            for item in (
                await session.scalars(
                    select(ConsentTextVersion).where(ConsentTextVersion.id.in_(text_ids))
                )
            ).all()
        }
        if text_ids
        else {}
    )
    current: dict[str, bool] = {}
    for consent_type in CONSENT_COPY:
        event = await _current_consent(session, consent_type, customer_id=customer_id)
        current[consent_type] = event.granted if event else False
    return {
        "items": [
            {"type": key, "granted": value, "description": CONSENT_COPY[key][1]}
            for key, value in current.items()
        ],
        "history": [_serialize_consent(event, texts) for event in events],
    }


@router.put("/consents/{consent_type}")
async def set_consent(
    consent_type: str,
    payload: ConsentInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, Any]:
    response.headers.update(PRIVATE_HEADERS)
    if consent_type not in CONSENT_COPY:
        raise DomainError("CONSENT_TYPE_UNKNOWN", "Nieznany rodzaj zgody.", 404)
    await _csrf(request, session)
    now = utc_now()
    version, copy = CONSENT_COPY[consent_type]
    async with session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        if customer is None or customer.deleted_at is not None:
            raise DomainError("ACCOUNT_UNAVAILABLE", "To konto jest niedostępne.", 401)
        latest = await _current_consent(session, consent_type, customer_id=customer_id)
        if latest is None or latest.granted != payload.granted:
            text_row = await _ensure_consent_text(session, consent_type, version, copy)
            row = CustomerConsent(
                customer_id=customer_id,
                subject_digest=consent_subject_digest(customer.email),
                consent_type=consent_type,
                granted=payload.granted,
                occurred_at=now,
                source="account_settings",
                consent_text_id=text_row.id,
                ip_hash=_ip_hash(request),
            )
            session.add(row)
            operation_id = uuid4()
            session.add(
                _audit(
                    customer_id,
                    "consent_changed",
                    operation_id,
                    {"consent_type": consent_type, "granted": payload.granted},
                )
            )
            await session.flush()
        else:
            row = latest
    return {
        "type": consent_type,
        "granted": row.granted,
        "occurred_at": row.occurred_at.isoformat(),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            key: _json_safe(item)
            for key, item in value.items()
            if key.lower() not in {"recipient_email", "recipient_name", "dedication", "gift_data"}
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _export_root() -> Path:
    uploads_root = Path(get_settings().UPLOADS_ROOT).expanduser().resolve()
    root = uploads_root / "privacy-exports"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.resolve().is_relative_to(uploads_root):
        raise OSError("private_export_root_invalid")
    with suppress(OSError):
        os.chmod(root, 0o700)
    return root.resolve()


def _export_path(customer_id: UUID, file_name: str) -> Path:
    if len(file_name) != 64 or any(char not in "0123456789abcdef" for char in file_name):
        raise ValueError("invalid_export_name")
    root = _export_root()
    directory = root / str(customer_id)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise OSError("private_export_path_invalid")
    path = directory / f"{file_name}.zip"
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise OSError("private_export_path_invalid")
    return path


async def _export_data(session: AsyncSession, customer_id: UUID) -> dict[str, Any]:
    from .models import ConsentTextVersion

    customer = await session.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise ValueError("account_unavailable")
    addresses = list(
        (
            await session.scalars(
                select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
            )
        ).all()
    )
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.customer_id == customer_id)
                .order_by(Order.created_at, Order.id)
            )
        ).all()
    )
    order_ids = [order.id for order in orders]
    order_items = (
        list(
            (
                await session.scalars(
                    select(OrderItem)
                    .where(OrderItem.order_id.in_(order_ids))
                    .order_by(OrderItem.order_id, OrderItem.id)
                )
            ).all()
        )
        if order_ids
        else []
    )
    consent_events = list(
        (
            await session.scalars(
                select(CustomerConsent)
                .where(CustomerConsent.customer_id == customer_id)
                .order_by(CustomerConsent.occurred_at, CustomerConsent.id)
            )
        ).all()
    )
    consent_text_ids = {event.consent_text_id for event in consent_events}
    text_map = (
        {
            row.id: row
            for row in (
                await session.scalars(
                    select(ConsentTextVersion).where(ConsentTextVersion.id.in_(consent_text_ids))
                )
            ).all()
        }
        if consent_text_ids
        else {}
    )
    vouchers = (
        list(
            (
                await session.scalars(
                    select(Voucher)
                    .join(OrderItem, OrderItem.id == Voucher.order_item_id)
                    .where(OrderItem.order_id.in_(order_ids))
                    .order_by(Voucher.issued_at, Voucher.id)
                )
            ).all()
        )
        if order_ids
        else []
    )
    shipments = (
        list(
            (await session.scalars(select(Shipment).where(Shipment.order_id.in_(order_ids)))).all()
        )
        if order_ids
        else []
    )
    return {
        "manifest": {
            "created_at": utc_now().isoformat(),
            "included": [
                "konto",
                "adresy",
                "zamówienia",
                "pozycje",
                "vouchery",
                "zgody",
                "przesyłki",
            ],
            "not_available": [
                "historia pobrań (brak modelu w bieżącym projekcie)",
                "dokumenty sprzedaży (brak modułu [36])",
            ],
            "third_party_fields_excluded": ["recipient_email", "recipient_name", "dedication"],
        },
        "account": {
            "id": str(customer.id),
            "email": customer.email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "phone": customer.phone,
            "email_verified_at": _json_safe(customer.email_verified_at),
            "created_at": _json_safe(customer.created_at),
            "last_login_at": _json_safe(customer.last_login_at),
        },
        "addresses": [
            {
                "label": row.label,
                "type": row.address_type,
                "default": row.is_default,
                "address": row.address_snapshot,
            }
            for row in addresses
        ],
        "orders": [
            {
                "id": str(row.id),
                "number": row.public_number,
                "created_at": _json_safe(row.created_at),
                "status": row.status,
                "fulfillment_status": row.fulfillment_status,
                "amount_due_grosz": row.amount_due_grosz,
                "payment_method": row.payment_method,
                "invoice": _json_safe(row.invoice_data),
                "shipping": _json_safe(row.shipping_data),
                "delivery_point": _json_safe(row.delivery_point_snapshot),
                "calculation": _json_safe(row.calculation_snapshot),
            }
            for row in orders
        ],
        "order_items": [
            {
                "id": str(row.id),
                "order_id": str(row.order_id),
                "product_id": str(row.product_id),
                "name": row.product_name_snapshot,
                "variant": _json_safe(row.voucher_snapshot),
                "quantity": row.quantity,
                "unit_price_grosz": row.unit_price_snapshot,
                "vat_rate": row.vat_rate_snapshot.value,
                "settlement": _json_safe(row.item_settlement),
            }
            for row in order_items
        ],
        "vouchers": [
            {
                "code": row.code,
                "status": row.status,
                "issued_at": _json_safe(row.issued_at),
                "valid_until": _json_safe(row.valid_until),
                "redeemed_at": _json_safe(row.redeemed_at),
                "variant": _json_safe(row.variant),
            }
            for row in vouchers
        ],
        "consents": [
            {**_serialize_consent(row, text_map), "text": text_map[row.consent_text_id].text}
            for row in consent_events
        ],
        "shipments": [
            {
                "order_id": str(row.order_id),
                "carrier": row.carrier,
                "tracking_number": row.tracking_number,
                "shipped_at": _json_safe(row.shipped_at),
                "delivered_at": _json_safe(row.delivered_at),
                "status": row.status,
            }
            for row in shipments
        ],
    }


async def _build_export(session_factory: async_sessionmaker[AsyncSession], job_id: UUID) -> None:
    async with session_factory() as session:
        job = await session.get(AccountPrivacyJob, job_id)
        if job is None:
            return
        customer_id = job.customer_id
        try:
            contents = await _export_data(session, customer_id)
        except Exception:
            await session.rollback()
            async with session.begin():
                row = await session.scalar(
                    select(AccountPrivacyJob)
                    .where(AccountPrivacyJob.id == job_id)
                    .with_for_update()
                )
                if row and row.status == "processing":
                    row.status = "failed"
                    row.error_code = "export_data_unavailable"
            return
    file_name = secrets.token_hex(32)
    target = _export_path(customer_id, file_name)
    descriptor, temp_name = tempfile.mkstemp(prefix=".pending-", dir=target.parent)
    try:
        with suppress(OSError):
            os.chmod(temp_name, 0o600)
        with (
            os.fdopen(descriptor, "wb") as raw,
            zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as archive,
        ):
            archive.writestr(
                "README.txt",
                (
                    "Eksport danych konta SENSORIA. Kwoty są zapisane w groszach, daty w ISO 8601 "
                    "z offsetem. Dane osób trzecich z dedykacji i odbiorców prezentów pominięto.\n"
                ),
            )
            archive.writestr(
                "data.json", json.dumps(contents, ensure_ascii=False, indent=2).encode("utf-8")
            )
        os.replace(temp_name, target)
        async with session_factory() as session, session.begin():
            customer = await session.get(Customer, customer_id)
            row = await session.scalar(
                select(AccountPrivacyJob).where(AccountPrivacyJob.id == job_id).with_for_update()
            )
            if (
                row is None
                or row.status != "processing"
                or customer is None
                or customer.deleted_at is not None
            ):
                target.unlink(missing_ok=True)
                if row is not None:
                    row.status = "cancelled"
                    row.error_code = "account_unavailable"
                return
            row.file_name = file_name
            row.status = "ready"
            row.completed_at = utc_now()
            row.expires_at = utc_now() + EXPORT_TTL
            session.add(_audit(customer_id, "privacy_export_prepared", row.id, {}))
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        async with session_factory() as session, session.begin():
            row = await session.scalar(
                select(AccountPrivacyJob).where(AccountPrivacyJob.id == job_id).with_for_update()
            )
            if row and row.status == "processing":
                row.status = "failed"
                row.error_code = "private_file_write_failed"


async def _process_deletion(
    session_factory: async_sessionmaker[AsyncSession], job_id: UUID
) -> None:
    async with session_factory() as session:
        job = await session.get(AccountPrivacyJob, job_id)
        if job is None:
            return
        customer_id = job.customer_id
    paths: list[Path] = []
    async with session_factory() as session, session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        row = await session.scalar(
            select(AccountPrivacyJob).where(AccountPrivacyJob.id == job_id).with_for_update()
        )
        if row is None or row.status not in {"pending", "processing"}:
            return
        # Revoke queued account mail and erase encrypted bearer payloads before dispatch.
        jobs = list(
            (
                await session.scalars(
                    select(AuthEmailJob)
                    .where(AuthEmailJob.customer_id == customer_id)
                    .with_for_update()
                )
            ).all()
        )
        for mail in jobs:
            if mail.status not in {"sent", "failed", "cancelled"}:
                mail.status = "cancelled"
                mail.failure_code = "account_deleted"
            mail.payload_ciphertext = ""
        now = utc_now()
        await session.execute(
            update(AccountSession)
            .where(AccountSession.customer_id == customer_id, AccountSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.execute(
            update(AccountActionToken)
            .where(
                AccountActionToken.customer_id == customer_id,
                AccountActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        await session.execute(
            update(LoginLink)
            .where(
                LoginLink.customer_id == customer_id,
                LoginLink.used_at.is_(None),
                LoginLink.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        await session.execute(
            update(AccountPrivacyJob)
            .where(
                AccountPrivacyJob.customer_id == customer_id,
                AccountPrivacyJob.kind == "export",
                AccountPrivacyJob.status.in_(("pending", "processing", "ready")),
            )
            .values(status="cancelled", error_code="account_deleted")
        )
        if customer is not None:
            await session.execute(
                delete(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
            )
            await session.execute(
                delete(CustomerBillingProfile).where(
                    CustomerBillingProfile.customer_id == customer_id
                )
            )
            # Remove raw email from consent evidence while retaining its immutable event,
            # text copy and keyed subject digest for restricted proof/chronology.
            await session.execute(
                update(CustomerConsent)
                .where(
                    (CustomerConsent.customer_id == customer_id)
                    | (CustomerConsent.email == customer.email)
                )
                .values(email=None)
            )
        export_names = list(
            (
                await session.scalars(
                    select(AccountPrivacyJob.file_name).where(
                        AccountPrivacyJob.customer_id == customer_id,
                        AccountPrivacyJob.kind == "export",
                        AccountPrivacyJob.file_name.is_not(None),
                    )
                )
            ).all()
        )
        for file_name in export_names:
            if file_name is None:
                continue
            try:
                paths.append(_export_path(customer_id, file_name))
            except (OSError, ValueError):
                row.status = "pending"
                row.available_at = now + timedelta(seconds=30)
                row.error_code = "private_file_cleanup_pending"
                return
        row.updated_at = now
    root = _export_root()
    directory = root / str(customer_id)
    if (
        directory.exists()
        and not directory.is_symlink()
        and directory.resolve().is_relative_to(root)
    ):
        try:
            for path in paths:
                if path.exists() and (path.is_symlink() or not path.resolve().is_relative_to(root)):
                    raise OSError("private_export_path_invalid")
                path.unlink(missing_ok=True)
        except OSError:
            async with session_factory() as session, session.begin():
                row = await session.scalar(
                    select(AccountPrivacyJob)
                    .where(AccountPrivacyJob.id == job_id)
                    .with_for_update()
                )
                if row and row.status == "processing":
                    row.status = "pending"
                    row.available_at = utc_now() + timedelta(seconds=30)
                    row.error_code = "private_file_cleanup_pending"
            return
        with suppress(OSError):
            directory.rmdir()
    async with session_factory() as session, session.begin():
        row = await session.scalar(
            select(AccountPrivacyJob).where(AccountPrivacyJob.id == job_id).with_for_update()
        )
        if row is not None and row.status == "processing":
            row.status = "complete"
            row.completed_at = utc_now()
            row.error_code = None
            session.add(_audit(customer_id, "privacy_deletion_cleanup_completed", row.id, {}))


async def process_privacy_jobs(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int = PRIVACY_BATCH_SIZE,
) -> int:
    """Claim durable jobs in PostgreSQL and perform bounded I/O outside transactions."""
    if not 1 <= batch_size <= 50:
        raise ValueError("batch_size poza dozwolonym zakresem")
    now = utc_now()
    claimed: list[tuple[UUID, str]] = []
    async with session_factory() as session, session.begin():
        stale_before = now - timedelta(minutes=15)
        rows = list(
            (
                await session.scalars(
                    select(AccountPrivacyJob)
                    .where(
                        (
                            (AccountPrivacyJob.status == "pending")
                            & (AccountPrivacyJob.available_at <= now)
                        )
                        | (
                            (AccountPrivacyJob.status == "processing")
                            & (AccountPrivacyJob.updated_at < stale_before)
                        )
                    )
                    .order_by(AccountPrivacyJob.created_at, AccountPrivacyJob.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for row in rows:
            if row.kind == "export":
                owner = await session.get(Customer, row.customer_id)
                if owner is None or owner.deleted_at is not None:
                    row.status = "cancelled"
                    row.error_code = "account_unavailable"
                    continue
            row.status = "processing"
            row.updated_at = now
            claimed.append((row.id, row.kind))
        expired = list(
            (
                await session.scalars(
                    select(AccountPrivacyJob)
                    .where(
                        AccountPrivacyJob.kind == "export",
                        AccountPrivacyJob.status == "ready",
                        AccountPrivacyJob.expires_at <= now,
                    )
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for row in expired:
            if row.file_name:
                try:
                    _export_path(row.customer_id, row.file_name).unlink(missing_ok=True)
                except OSError:
                    row.error_code = "expired_file_cleanup_pending"
                    continue
            row.status = "complete"
            row.file_name = None
            row.error_code = "export_expired"
    for job_id, kind in claimed:
        if kind == "export":
            await _build_export(session_factory, job_id)
        else:
            await _process_deletion(session_factory, job_id)
    return len(claimed)


async def privacy_job_scheduler() -> None:
    """Single-process polling loop; PostgreSQL SKIP LOCKED coordinates replicas."""
    while True:
        try:
            await process_privacy_jobs()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("account_privacy_job_batch_failed")
        await asyncio.sleep(5)


@router.post("/export")
async def request_export(
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, Any]:
    response.headers.update(PRIVATE_HEADERS)
    await _csrf(request, session)
    now = utc_now()
    async with session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        if customer is None or customer.deleted_at is not None:
            raise DomainError("ACCOUNT_UNAVAILABLE", "To konto jest niedostępne.", 401)
        prior = await session.scalar(
            select(AccountPrivacyJob)
            .where(
                AccountPrivacyJob.customer_id == customer_id,
                AccountPrivacyJob.kind == "export",
                AccountPrivacyJob.created_at >= now - EXPORT_COOLDOWN,
            )
            .order_by(AccountPrivacyJob.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if prior is None:
            prior = AccountPrivacyJob(customer_id=customer_id, kind="export", status="pending")
            session.add(prior)
            await session.flush()
            session.add(_audit(customer_id, "privacy_export_requested", prior.id, {}))
        elif prior.status in {"failed", "complete", "cancelled"}:
            prior.status = "pending"
            prior.error_code = None
            prior.completed_at = None
            prior.expires_at = None
            prior.available_at = now
    return {"id": str(prior.id), "status": prior.status, "message": "Przygotujemy archiwum w tle."}


@router.get("/export/{job_id}")
async def export_status(
    job_id: UUID, response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, Any]:
    response.headers.update(PRIVATE_HEADERS)
    row = await session.scalar(
        select(AccountPrivacyJob).where(
            AccountPrivacyJob.id == job_id,
            AccountPrivacyJob.customer_id == customer_id,
            AccountPrivacyJob.kind == "export",
        )
    )
    if row is None:
        raise DomainError("PRIVACY_EXPORT_NOT_FOUND", "Nie znaleziono eksportu.", 404)
    return {
        "id": str(row.id),
        "status": row.status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "error": row.error_code,
    }


@router.get("/export/{job_id}/download")
async def download_export(
    job_id: UUID, response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> FileResponse:
    response.headers.update(PRIVATE_HEADERS)
    row = await session.scalar(
        select(AccountPrivacyJob).where(
            AccountPrivacyJob.id == job_id,
            AccountPrivacyJob.customer_id == customer_id,
            AccountPrivacyJob.kind == "export",
        )
    )
    if (
        row is None
        or row.status != "ready"
        or row.expires_at is None
        or row.expires_at <= utc_now()
        or not row.file_name
    ):
        raise DomainError("PRIVACY_EXPORT_NOT_READY", "Archiwum jest niedostępne lub wygasło.", 404)
    if row.status == "ready":
        session.add(_audit(customer_id, "privacy_export_downloaded", row.id, {}))
        await session.commit()
    try:
        path = _export_path(customer_id, row.file_name)
    except (OSError, ValueError):
        raise DomainError("PRIVACY_EXPORT_NOT_FOUND", "Archiwum jest niedostępne.", 404) from None
    if not path.is_file():
        raise DomainError("PRIVACY_EXPORT_NOT_FOUND", "Archiwum jest niedostępne.", 404)
    return FileResponse(
        path,
        media_type="application/zip",
        filename="sensoria-eksport-danych.zip",
        headers=PRIVATE_HEADERS,
    )


@router.post("/delete")
async def request_account_deletion(
    payload: DeleteAccountInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, str]:
    await _csrf(request, session)
    now = utc_now()
    session_id = getattr(request.state, "account_session_id", None)
    async with session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        current = await session.scalar(
            select(AccountSession)
            .where(
                AccountSession.id == session_id,
                AccountSession.customer_id == customer_id,
                AccountSession.revoked_at.is_(None),
                AccountSession.absolute_expires_at > now,
            )
            .with_for_update()
        )
        if customer is None or customer.deleted_at is not None or current is None:
            raise DomainError("ACCOUNT_UNAVAILABLE", "To konto jest niedostępne.", 401)
        if current.reauthenticated_at is None or current.reauthenticated_at < now - DELETE_REAUTH:
            raise DomainError(
                "RECENT_AUTH_REQUIRED",
                "Potwierdź ponownie swoją tożsamość przed zamknięciem konta.",
                403,
            )
        if not hmac.compare_digest(customer.email, payload.email):
            raise DomainError(
                "ACCOUNT_EMAIL_CONFIRMATION_MISMATCH",
                "Wpisany adres nie jest aktualnym adresem konta.",
                422,
            )
        digest = deleted_email_digest(customer.email)
        session.add(DeletedEmailSuppression(email_digest=digest))
        old_email = customer.email
        customer.deleted_at = now
        customer.email = f"deleted-{customer.id.hex}@account.invalid"
        customer.pending_email = None
        customer.first_name = "Usunięte"
        customer.last_name = "konto"
        customer.phone = None
        customer.password_hash = "!account-closed!"
        customer.email_verified_at = None
        await session.execute(
            update(AccountSession)
            .where(AccountSession.customer_id == customer_id, AccountSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.execute(
            update(AccountActionToken)
            .where(
                AccountActionToken.customer_id == customer_id,
                AccountActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        await session.execute(
            update(LoginLink)
            .where(
                LoginLink.customer_id == customer_id,
                LoginLink.used_at.is_(None),
                LoginLink.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        await session.execute(
            update(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer_id,
                AuthEmailJob.status.in_(("pending", "queued")),
            )
            .values(status="cancelled", failure_code="account_closed", payload_ciphertext="")
        )
        await session.execute(
            update(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer_id,
                AuthEmailJob.status.in_(("sent", "failed", "cancelled")),
            )
            .values(payload_ciphertext="")
        )
        # Avoid a guest checkout's old email being attached back to this closed account.
        await session.execute(
            delete(CustomerConsent).where(
                CustomerConsent.customer_id.is_(None), CustomerConsent.email == old_email
            )
        )
        await session.execute(
            update(CustomerConsent)
            .where(CustomerConsent.customer_id == customer_id)
            .values(email=None)
        )
        await session.execute(
            delete(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
        )
        await session.execute(
            delete(CustomerBillingProfile).where(CustomerBillingProfile.customer_id == customer_id)
        )
        await session.execute(
            update(AccountPrivacyJob)
            .where(
                AccountPrivacyJob.customer_id == customer_id,
                AccountPrivacyJob.kind == "export",
                AccountPrivacyJob.status.in_(("pending", "processing", "ready")),
            )
            .values(status="cancelled", error_code="account_closed")
        )
        deletion = AccountPrivacyJob(customer_id=customer_id, kind="deletion", status="pending")
        session.add(deletion)
        await session.flush()
        session.add(_audit(customer_id, "account_deletion_confirmed", deletion.id, {}))
    response.delete_cookie(
        SESSION_COOKIE,
        path="/api",
        secure=get_settings().ENVIRONMENT == "production",
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/api",
        secure=get_settings().ENVIRONMENT == "production",
        httponly=False,
        samesite="lax",
    )
    response.headers.update(PRIVATE_HEADERS)
    return {
        "status": "processing",
        "message": "Konto zostało zamknięte. Dostęp wyłączono; kończymy usuwanie plików danych.",
    }


@router.get("/deletion-status/{job_id}")
async def deletion_status(
    job_id: UUID, response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, str]:
    response.headers.update(PRIVATE_HEADERS)
    row = await session.scalar(
        select(AccountPrivacyJob).where(
            AccountPrivacyJob.id == job_id,
            AccountPrivacyJob.customer_id == customer_id,
            AccountPrivacyJob.kind == "deletion",
        )
    )
    if row is None:
        raise DomainError("PRIVACY_DELETION_NOT_FOUND", "Nie znaleziono procesu.", 404)
    return {"status": row.status, "error": row.error_code or ""}
