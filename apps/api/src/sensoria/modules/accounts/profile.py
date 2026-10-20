"""Private customer profile and saved delivery-address operations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.modules.orders.models import Order
from sensoria.modules.orders.pickup_points import get_point
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .address_fingerprint import address_fingerprint
from .auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    digest_secret,
    normalize_email,
    require_customer_id,
)
from .clock import utc_now
from .models import (
    AccountActionToken,
    AccountSession,
    AuthEmailJob,
    Customer,
    CustomerAddress,
    LoginLink,
)
from .purchase_linking import reconcile_guest_purchases

router = APIRouter(tags=["account-profile"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, Authorization",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("To pole jest wymagane.")
        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if normalized and (len(normalized) < 5 or any(ord(char) < 32 for char in normalized)):
            raise ValueError("Podaj prawidłowy numer telefonu.")
        return normalized or None


class EmailChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)


class EmailConfirmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=100)


class AddressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=80)
    address_type: Literal["address", "parcel_locker"]
    street: str | None = Field(default=None, max_length=180)
    building_number: str | None = Field(default=None, max_length=20)
    apartment_number: str | None = Field(default=None, max_length=20)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    country: str = Field(default="PL", min_length=2, max_length=2)
    point_code: str | None = Field(default=None, max_length=20)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Podaj nazwę adresu.")
        return value

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_shape(self) -> AddressInput:
        if self.address_type == "address":
            if not all((self.street, self.building_number, self.postal_code, self.city)):
                raise ValueError("Uzupełnij ulicę, numer budynku, kod pocztowy i miasto.")
            if self.point_code or self.apartment_number and not self.building_number:
                raise ValueError("Zwykły adres nie może zawierać kodu Paczkomatu.")
        elif not self.point_code or any(
            (self.street, self.building_number, self.apartment_number, self.postal_code, self.city)
        ):
            raise ValueError("Dla Paczkomatu podaj wyłącznie kod potwierdzonego punktu.")
        return self


def _serialized_address(row: CustomerAddress) -> dict[str, Any]:
    snapshot = row.address_snapshot if isinstance(row.address_snapshot, dict) else {}
    return {
        "id": str(row.id),
        "label": row.label,
        "address_type": row.address_type,
        "is_default": row.is_default,
        **snapshot,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


async def _duplicate_address_exists(
    session: AsyncSession,
    customer_id: UUID,
    address_type: str,
    snapshot: dict[str, Any],
    *,
    exclude_id: UUID | None = None,
) -> bool:
    rows = list(
        (
            await session.scalars(
                select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
            )
        ).all()
    )
    fingerprint = address_fingerprint(address_type, snapshot)
    return any(
        row.id != exclude_id
        and row.address_type == address_type
        and address_fingerprint(address_type, row.address_snapshot) == fingerprint
        for row in rows
    )


def _audit(customer_id: UUID, action: str, entity_id: UUID, payload: dict[str, Any]) -> AuditLog:
    return AuditLog(
        actor_type=ActorType.CUSTOMER,
        actor_id=customer_id,
        entity_type="customer",
        entity_id=customer_id,
        action=action,
        payload={"operation_id": str(entity_id), **payload},
    )


def _encrypt_mail_payload(payload: dict[str, str]) -> str:
    key = hashlib.sha256(
        get_settings().SECRET_KEY.get_secret_value().encode() + b"sensoria-auth-mail-v1"
    ).digest()
    nonce = secrets.token_bytes(12)
    raw = AESGCM(key).encrypt(
        nonce, json.dumps(payload, ensure_ascii=False).encode(), b"auth-email-v1"
    )
    return base64.urlsafe_b64encode(nonce + raw).decode()


async def _require_csrf(request: Request, session: AsyncSession, header: str | None) -> None:
    from .router import _require_csrf as require_csrf

    await require_csrf(request, session, header)
    # require_csrf may query the active session and begin an implicit transaction;
    # profile mutations open explicit transaction scopes below.
    await session.commit()


def _secure_cookie(response: Response, name: str, value: str, max_age: int | None = None) -> None:
    from .router import _secure_cookie as secure_cookie

    secure_cookie(response, name, value, max_age)


def _delete_cookie(response: Response, name: str) -> None:
    from .router import _delete_cookie as delete_cookie

    delete_cookie(response, name)


@router.get("/profile")
async def get_profile(
    response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, Any]:
    response.headers.update(PRIVATE_HEADERS)
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise DomainError("ACCOUNT_NOT_FOUND", "Nie znaleziono konta.", 404)
    addresses = list(
        (
            await session.scalars(
                select(CustomerAddress)
                .where(CustomerAddress.customer_id == customer_id)
                .order_by(
                    CustomerAddress.is_default.desc(),
                    CustomerAddress.created_at,
                    CustomerAddress.id,
                )
            )
        ).all()
    )
    help_setting = await session.scalar(
        select(AppSetting).where(AppSetting.key == "vouchers.public.v1")
    )
    help_value = help_setting.value if help_setting is not None else {}
    contact_email = (
        " ".join(help_value.get("contact_email", "").split())[:320] or None
        if isinstance(help_value, dict) and isinstance(help_value.get("contact_email"), str)
        else None
    )
    contact_phone = (
        " ".join(help_value.get("contact_phone", "").split())[:40] or None
        if isinstance(help_value, dict) and isinstance(help_value.get("contact_phone"), str)
        else None
    )
    first_purchase_at = await session.scalar(
        select(func.min(Order.created_at)).where(
            Order.customer_id == customer_id, Order.status == "paid"
        )
    )
    return {
        "id": str(customer.id),
        "email": customer.email,
        "pending_email": customer.pending_email,
        "email_verified": customer.email_verified_at is not None,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "phone": customer.phone,
        "first_purchase_at": first_purchase_at.isoformat() if first_purchase_at else None,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "addresses": [_serialized_address(address) for address in addresses],
    }


@router.put("/profile/personal")
async def update_personal_data(
    payload: ProfileInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, str | None]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    async with session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        if customer is None:
            raise DomainError("ACCOUNT_NOT_FOUND", "Nie znaleziono konta.", 404)
        changed = [
            key
            for key, value in (
                ("first_name", payload.first_name),
                ("last_name", payload.last_name),
                ("phone", payload.phone),
            )
            if getattr(customer, key) != value
        ]
        customer.first_name = payload.first_name
        customer.last_name = payload.last_name
        customer.phone = payload.phone
        if changed:
            session.add(
                _audit(customer_id, "profile_updated", uuid4(), {"changed_fields": changed})
            )
    response.headers.update(PRIVATE_HEADERS)
    return {
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "phone": payload.phone,
    }


@router.get("/checkout-defaults")
async def checkout_defaults(
    response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, Any]:
    """Suggest saved values to an authenticated checkout; callers can keep their edits."""
    response.headers.update(PRIVATE_HEADERS)
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise DomainError("ACCOUNT_NOT_FOUND", "Nie znaleziono konta.", 404)
    rows = list(
        (
            await session.scalars(
                select(CustomerAddress)
                .where(CustomerAddress.customer_id == customer_id)
                .order_by(
                    CustomerAddress.is_default.desc(),
                    CustomerAddress.created_at,
                    CustomerAddress.id,
                )
            )
        ).all()
    )
    return {
        "email": customer.email,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "phone": customer.phone,
        "addresses": [_serialized_address(row) for row in rows],
    }


@router.post("/profile/email-change")
async def request_email_change(
    payload: EmailChangeInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, str | None]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    target = normalize_email(payload.email)
    now = utc_now()
    session_id = getattr(request.state, "account_session_id", None)
    async with session.begin():
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        account_session = await session.scalar(
            select(AccountSession)
            .where(
                AccountSession.id == session_id,
                AccountSession.customer_id == customer_id,
                AccountSession.revoked_at.is_(None),
                AccountSession.absolute_expires_at > now,
            )
            .with_for_update()
        )
        if customer is None or account_session is None:
            raise DomainError("AUTHENTICATION_REQUIRED", "Zaloguj się ponownie.", 401)
        if (
            account_session.reauthenticated_at is None
            or account_session.reauthenticated_at < now - timedelta(minutes=10)
        ):
            raise DomainError(
                "RECENT_AUTH_REQUIRED",
                "Zaloguj się ponownie przed zmianą adresu e-mail.",
                403,
            )
        if target == customer.email:
            return {
                "pending_email": customer.pending_email,
                "message": "To już jest aktualny adres e-mail.",
            }
        if await session.scalar(select(Customer.id).where(Customer.email == target)):
            raise DomainError("EMAIL_ALREADY_USED", "Ten adres e-mail jest już używany.", 409)

        await session.execute(
            update(AccountActionToken)
            .where(
                AccountActionToken.customer_id == customer.id,
                AccountActionToken.purpose == "email_change",
                AccountActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        await session.execute(
            update(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer.id,
                AuthEmailJob.purpose == "email_change",
                AuthEmailJob.status.in_(("pending", "queued")),
            )
            .values(status="cancelled", failure_code="superseded")
        )
        selector = secrets.token_urlsafe(16)
        secret = secrets.token_urlsafe(32)
        token = f"{selector}.{secret}"
        customer.pending_email = target
        session.add(
            AccountActionToken(
                customer_id=customer_id,
                selector=selector,
                secret_hash=digest_secret(secret),
                purpose="email_change",
                target_email=target,
                expires_at=now + timedelta(hours=24),
            )
        )
        job = AuthEmailJob(
            customer_id=customer_id,
            purpose="email_change",
            payload_ciphertext=_encrypt_mail_payload(
                {"to": target, "token": token, "old_email": customer.email}
            ),
            idempotency_key=f"email_change:{selector}",
        )
        session.add(job)
        session.add(
            _audit(customer_id, "email_change_requested", uuid4(), {"changed_fields": ["email"]})
        )
    response.headers.update(PRIVATE_HEADERS)
    return {"pending_email": target, "message": "Wysłaliśmy prośbę o potwierdzenie nowego adresu."}


@router.post("/profile/email-change/confirm")
async def confirm_email_change(
    payload: EmailConfirmInput,
    request: Request,
    response: Response,
    session: SessionDependency,
) -> dict[str, str | bool]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    try:
        selector, secret = payload.token.split(".", 1)
    except ValueError:
        raise DomainError(
            "EMAIL_CHANGE_LINK_INVALID", "Link jest nieprawidłowy lub wygasł.", 422
        ) from None
    now = utc_now()
    raw_session = request.cookies.get(SESSION_COOKIE)
    session_id: UUID | None = None
    new_secret: str | None = None
    new_csrf: str | None = None
    cookie_max_age: int | None = None
    session_preserved = False
    async with session.begin():
        token_hint = await session.scalar(
            select(AccountActionToken).where(
                AccountActionToken.selector == selector,
                AccountActionToken.purpose == "email_change",
            )
        )
        if token_hint is None:
            raise DomainError(
                "EMAIL_CHANGE_LINK_INVALID", "Link jest nieprawidłowy lub wygasł.", 422
            )
        customer_id = token_hint.customer_id
        customer = await session.scalar(
            select(Customer).where(Customer.id == customer_id).with_for_update()
        )
        token = await session.scalar(
            select(AccountActionToken)
            .where(
                AccountActionToken.selector == selector,
                AccountActionToken.purpose == "email_change",
                AccountActionToken.customer_id == customer_id,
                AccountActionToken.consumed_at.is_(None),
                AccountActionToken.expires_at > now,
            )
            .with_for_update()
        )
        if (
            customer is None
            or token is None
            or token.target_email is None
            or (
                customer.pending_email != token.target_email
                or not hmac.compare_digest(token.secret_hash, digest_secret(secret))
            )
        ):
            raise DomainError(
                "EMAIL_CHANGE_LINK_INVALID", "Link jest nieprawidłowy lub wygasł.", 422
            )
        current_session: AccountSession | None = None
        if raw_session:
            current_session = await session.scalar(
                select(AccountSession)
                .where(
                    AccountSession.secret_hash == digest_secret(raw_session),
                    AccountSession.revoked_at.is_(None),
                    AccountSession.idle_expires_at > now,
                    AccountSession.absolute_expires_at > now,
                )
                .with_for_update()
            )
        if current_session is not None and current_session.customer_id != customer_id:
            raise DomainError(
                "OTHER_ACCOUNT_SESSION_ACTIVE",
                "Wyloguj się z innego konta przed potwierdzeniem zmiany adresu.",
                409,
            )
        if current_session is not None:
            session_id = current_session.id
            session_preserved = True
        if await session.scalar(select(Customer.id).where(Customer.email == token.target_email)):
            raise DomainError("EMAIL_ALREADY_USED", "Ten adres e-mail jest już używany.", 409)

        # Reconcile any still-eligible guest purchases for the verified old email
        # before changing the account identifier. Owned records remain keyed by customer_id.
        await reconcile_guest_purchases(session, customer_id, source="email_verification", at=now)

        try:
            async with session.begin_nested():
                customer.email = token.target_email
                customer.email_verified_at = now
                customer.pending_email = None
                token.consumed_at = now
                await session.flush()
        except IntegrityError:
            raise DomainError(
                "EMAIL_ALREADY_USED", "Ten adres e-mail jest już używany.", 409
            ) from None

        await session.execute(
            update(AccountActionToken)
            .where(
                AccountActionToken.customer_id == customer_id,
                AccountActionToken.id != token.id,
                AccountActionToken.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        await session.execute(
            update(LoginLink)
            .where(LoginLink.customer_id == customer_id, LoginLink.used_at.is_(None))
            .values(invalidated_at=now)
        )
        await session.execute(
            update(AuthEmailJob)
            .where(
                AuthEmailJob.customer_id == customer_id,
                AuthEmailJob.purpose == "email_change",
                AuthEmailJob.idempotency_key == f"email_change:{selector}",
                AuthEmailJob.status.in_(("pending", "queued")),
            )
            .values(status="cancelled", failure_code="token_consumed")
        )
        session_update = update(AccountSession).where(AccountSession.customer_id == customer_id)
        if session_id is not None:
            session_update = session_update.where(AccountSession.id != session_id)
        await session.execute(session_update.values(revoked_at=now))
        if current_session is not None:
            new_secret = secrets.token_urlsafe(32)
            new_csrf = secrets.token_urlsafe(32)
            current_session.secret_hash = digest_secret(new_secret)
            current_session.csrf_hash = hashlib.sha256(new_csrf.encode()).hexdigest()
            current_session.reauthenticated_at = now
            current_session.last_seen_at = now
            cookie_max_age = int(
                max(
                    1,
                    (
                        current_session.absolute_expires_at
                        if current_session.remember_me
                        else current_session.idle_expires_at
                    ).timestamp()
                    - now.timestamp(),
                )
            )
        session.add(
            _audit(customer_id, "email_change_confirmed", uuid4(), {"changed_fields": ["email"]})
        )
    if new_secret is not None and new_csrf is not None:
        _secure_cookie(response, SESSION_COOKIE, new_secret, cookie_max_age)
        _secure_cookie(response, CSRF_COOKIE, new_csrf, 86400)
    else:
        _delete_cookie(response, SESSION_COOKIE)
        _delete_cookie(response, CSRF_COOKIE)
    response.headers.update(PRIVATE_HEADERS)
    return {
        "message": (
            "Adres e-mail został potwierdzony i zmieniony."
            if session_preserved
            else "Adres e-mail został potwierdzony. Zaloguj się nowym adresem."
        ),
        "session_preserved": session_preserved,
    }


async def _validated_snapshot(payload: AddressInput) -> dict[str, Any]:
    if payload.address_type == "parcel_locker":
        assert payload.point_code is not None
        point = await get_point(payload.point_code)
        return {
            "code": point.code,
            "name": point.name,
            "street": point.street,
            "postal_code": point.postal_code,
            "city": point.city,
            "opening_hours": point.opening_hours,
            "verified_at": point.verified_at.isoformat(),
        }
    assert payload.street and payload.building_number and payload.postal_code and payload.city
    street = " ".join(
        value for value in (payload.street.strip(), payload.building_number.strip()) if value
    )
    if payload.apartment_number:
        street += f"/{payload.apartment_number.strip()}"
    return {
        "street": street,
        "building_number": payload.building_number.strip(),
        "apartment_number": payload.apartment_number.strip() if payload.apartment_number else None,
        "postal_code": payload.postal_code.strip(),
        "city": " ".join(payload.city.split()),
        "country": payload.country,
    }


async def _lock_customer(session: AsyncSession, customer_id: UUID) -> Customer:
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None:
        raise DomainError("ACCOUNT_NOT_FOUND", "Nie znaleziono konta.", 404)
    return customer


@router.get("/profile/addresses")
async def list_addresses(
    response: Response, session: SessionDependency, customer_id: CustomerDependency
) -> dict[str, list[dict[str, Any]]]:
    response.headers.update(PRIVATE_HEADERS)
    rows = list(
        (
            await session.scalars(
                select(CustomerAddress)
                .where(CustomerAddress.customer_id == customer_id)
                .order_by(
                    CustomerAddress.is_default.desc(),
                    CustomerAddress.created_at,
                    CustomerAddress.id,
                )
            )
        ).all()
    )
    return {"items": [_serialized_address(row) for row in rows]}


@router.post("/profile/addresses", status_code=201)
async def create_address(
    payload: AddressInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, Any]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    snapshot = await _validated_snapshot(payload)
    async with session.begin():
        await _lock_customer(session, customer_id)
        rows = list(
            (
                await session.scalars(
                    select(CustomerAddress)
                    .where(CustomerAddress.customer_id == customer_id)
                    .order_by(CustomerAddress.created_at, CustomerAddress.id)
                    .with_for_update()
                )
            ).all()
        )
        fingerprint = address_fingerprint(payload.address_type, snapshot)
        if any(
            row.address_type == payload.address_type
            and address_fingerprint(payload.address_type, row.address_snapshot) == fingerprint
            for row in rows
        ):
            raise DomainError(
                "ADDRESS_ALREADY_SAVED", "Ten adres jest już zapisany na koncie.", 409
            )
        address = CustomerAddress(
            customer_id=customer_id,
            source_order_id=None,
            label=payload.label,
            address_type=payload.address_type,
            is_default=not rows,
            fingerprint=fingerprint,
            address_snapshot=snapshot,
        )
        session.add(address)
        session.add(
            _audit(
                customer_id, "address_created", address.id, {"address_type": payload.address_type}
            )
        )
        await session.flush()
    response.headers.update(PRIVATE_HEADERS)
    return _serialized_address(address)


@router.put("/profile/addresses/{address_id}")
async def edit_address(
    address_id: UUID,
    payload: AddressInput,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, Any]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    snapshot = await _validated_snapshot(payload)
    async with session.begin():
        await _lock_customer(session, customer_id)
        row = await session.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.id == address_id, CustomerAddress.customer_id == customer_id)
            .with_for_update()
        )
        if row is None:
            raise DomainError("ADDRESS_NOT_FOUND", "Nie znaleziono tego adresu.", 404)
        if await _duplicate_address_exists(
            session,
            customer_id,
            payload.address_type,
            snapshot,
            exclude_id=row.id,
        ):
            raise DomainError(
                "ADDRESS_ALREADY_SAVED", "Ten adres jest już zapisany na koncie.", 409
            )
        row.label = payload.label
        row.address_type = payload.address_type
        row.address_snapshot = snapshot
        row.fingerprint = address_fingerprint(payload.address_type, snapshot)
        session.add(
            _audit(customer_id, "address_updated", row.id, {"address_type": payload.address_type})
        )
        await session.flush()
    response.headers.update(PRIVATE_HEADERS)
    return _serialized_address(row)


@router.post("/profile/addresses/{address_id}/default")
async def set_default_address(
    address_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, str]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    async with session.begin():
        await _lock_customer(session, customer_id)
        rows = list(
            (
                await session.scalars(
                    select(CustomerAddress)
                    .where(CustomerAddress.customer_id == customer_id)
                    .order_by(CustomerAddress.created_at, CustomerAddress.id)
                    .with_for_update()
                )
            ).all()
        )
        target = next((row for row in rows if row.id == address_id), None)
        if target is None:
            raise DomainError("ADDRESS_NOT_FOUND", "Nie znaleziono tego adresu.", 404)
        await session.execute(
            update(CustomerAddress)
            .where(CustomerAddress.customer_id == customer_id)
            .values(is_default=False)
        )
        target.is_default = True
        session.add(
            _audit(
                customer_id,
                "address_default_changed",
                address_id,
                {"changed_fields": ["is_default"]},
            )
        )
    response.headers.update(PRIVATE_HEADERS)
    return {"message": "Zmieniono domyślny adres."}


@router.delete("/profile/addresses/{address_id}")
async def delete_address(
    address_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, str]:
    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    async with session.begin():
        await _lock_customer(session, customer_id)
        rows = list(
            (
                await session.scalars(
                    select(CustomerAddress)
                    .where(CustomerAddress.customer_id == customer_id)
                    .order_by(CustomerAddress.created_at, CustomerAddress.id)
                    .with_for_update()
                )
            ).all()
        )
        target = next((row for row in rows if row.id == address_id), None)
        if target is None:
            raise DomainError("ADDRESS_NOT_FOUND", "Nie znaleziono tego adresu.", 404)
        was_default = target.is_default
        survivors = [row for row in rows if row.id != target.id]
        if was_default and survivors:
            target.is_default = False
            await session.flush()
            survivors[0].is_default = True
        session.add(
            _audit(
                customer_id, "address_deleted", address_id, {"address_type": target.address_type}
            )
        )
        await session.delete(target)
    response.headers.update(PRIVATE_HEADERS)
    return {"message": "Adres został usunięty."}
