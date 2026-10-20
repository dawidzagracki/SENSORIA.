"""Authenticated customer voucher list and actions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

import qrcode
from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from qrcode.constants import ERROR_CORRECT_Q
from qrcode.image.svg import SvgPathImage
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.modules.catalog.models import Product
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.orders.router import _COOKIE_NAME, _set_cart_cookie
from sensoria.modules.orders.service import reorder_voucher
from sensoria.modules.storage.models import StoredFile
from sensoria.modules.storage.service import StorageService
from sensoria.modules.vouchers.models import Voucher, VoucherExtensionRequest, VoucherPDFJob
from sensoria.modules.vouchers.service import days_until_expiry, effective_voucher_status
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .auth import require_customer_id
from .models import Customer

router = APIRouter(prefix="/vouchers", tags=["account-vouchers"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


class AccountVoucher(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    code: str
    status: str
    name: str
    variant: str
    issued_at: datetime
    valid_until: datetime
    days_until_expiry: int
    redeemed_at: datetime | None
    redeemed_by: str | None
    place: str | None
    purchase_date: datetime
    pdf_status: str
    qr_path: str
    product_path: str | None
    variant_id: UUID | None = None
    request_pending: bool
    requests: list[dict[str, Any]]


class AccountVouchersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str | None
    first_purchase_at: datetime | None
    items: list[AccountVoucher]
    total_count: int
    usable_count: int
    purchase_history_notice: bool
    contact_email: str | None
    contact_phone: str | None
    booking_url: str | None
    booking_instructions: str | None


class ExtensionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(default="", max_length=2000)


def _setting_origin() -> str:
    settings = get_settings()
    raw = settings.SITE_URL or ""
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        raise DomainError(
            "VOUCHER_LINK_UNAVAILABLE",
            "Link vouchera jest niedostępny.",
            503,
            headers=PRIVATE_HEADERS,
        )
    return f"{parsed.scheme}://{parsed.netloc}"


async def _read_help_settings(session: AsyncSession) -> dict[str, Any]:
    record = await session.scalar(select(AppSetting).where(AppSetting.key == "vouchers.public.v1"))
    if record is None or not isinstance(record.value, dict):
        return {}
    return record.value


def _safe_optional_text(value: Any, max_length: int = 1000) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())[:max_length]
    return normalized or None


def _safe_booking_url(value: Any) -> str | None:
    candidate = _safe_optional_text(value, 1000)
    if candidate is None:
        return None
    try:
        parsed = urlsplit(candidate)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return candidate


@router.get("", response_model=AccountVouchersResponse)
async def list_account_vouchers(
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> AccountVouchersResponse:
    """Return every paid voucher owned by the authenticated customer account."""

    response.headers.update(
        {
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "Vary": "Cookie, Authorization",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        }
    )
    rows = (
        await session.execute(
            select(Voucher, Order, OrderItem, Product, VoucherPDFJob)
            .join(OrderItem, OrderItem.id == Voucher.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == Voucher.product_id)
            .outerjoin(VoucherPDFJob, VoucherPDFJob.voucher_id == Voucher.id)
            .where(Order.customer_id == customer_id, Order.status == "paid")
            .order_by(Voucher.issued_at.desc(), Voucher.id)
        )
    ).all()
    customer = await session.get(Customer, customer_id)

    voucher_ids = [voucher.id for voucher, *_rest in rows]
    requests_by_voucher: dict[UUID, list[dict[str, Any]]] = {
        voucher_id: [] for voucher_id in voucher_ids
    }
    if voucher_ids:
        request_rows = (
            (
                await session.execute(
                    select(VoucherExtensionRequest)
                    .where(
                        VoucherExtensionRequest.voucher_id.in_(voucher_ids),
                        VoucherExtensionRequest.customer_id == customer_id,
                    )
                    .order_by(VoucherExtensionRequest.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        for request_item in request_rows:
            requests_by_voucher[request_item.voucher_id].append(
                {
                    "created_at": request_item.created_at,
                    "status": request_item.status,
                    "message": request_item.message,
                }
            )

    items: list[AccountVoucher] = []
    usable_count = 0
    for voucher, order, order_item, product, pdf_job in rows:
        status = effective_voucher_status(voucher)
        if status in {"active", "expiring_soon"}:
            usable_count += 1
        snapshot = voucher.issue_snapshot
        variant_kind = snapshot.get("variant_kind")
        variant_label = "Online" if variant_kind == "ONLINE" else "W gabinecie"
        variant_key = {"IN_PERSON": "gabinet", "ONLINE": "online"}.get(variant_kind)
        product_name = _safe_optional_text(snapshot.get("product_name"), 200)
        name = (
            _safe_optional_text(snapshot.get("service_name"), 200)
            or product_name
            or "Voucher na wizytę"
        )
        pdf_status = (
            "ready"
            if voucher.pdf_file_id is not None
            else (
                "preparing"
                if pdf_job is not None and pdf_job.status in {"pending", "processing"}
                else "failed"
                if pdf_job is not None and pdf_job.status == "failed"
                else "missing"
            )
        )
        request_history = requests_by_voucher.get(voucher.id, [])
        items.append(
            AccountVoucher(
                id=voucher.id,
                code=voucher.code,
                status=status,
                name=name,
                variant=variant_label,
                issued_at=voucher.issued_at,
                valid_until=voucher.valid_until,
                days_until_expiry=days_until_expiry(voucher.valid_until),
                redeemed_at=voucher.redeemed_at,
                redeemed_by=_safe_optional_text(voucher.redeemed_by, 200),
                # This is the purchased service location, not a claimed redemption venue.
                place="Gabinet — szczegóły w dokumencie"
                if variant_kind == "IN_PERSON"
                else "Realizacja online",
                purchase_date=order.created_at,
                pdf_status=pdf_status,
                qr_path=f"/api/accounts/vouchers/{voucher.id}/qr",
                product_path=(
                    f"/sklep/{product.slug}?variant={variant_key}"
                    if product.status == "PUBLISHED" and variant_key is not None
                    else None
                ),
                variant_id=order_item.variant_id,
                request_pending=any(entry["status"] == "pending" for entry in request_history),
                requests=request_history,
            )
        )

    help_config = await _read_help_settings(session)
    first_purchase = await session.scalar(
        select(func.min(Order.created_at)).where(
            Order.customer_id == customer_id, Order.status == "paid"
        )
    )
    return AccountVouchersResponse(
        customer_name=(
            f"{customer.first_name} {customer.last_name}" if customer is not None else None
        ),
        first_purchase_at=first_purchase,
        items=items,
        total_count=len(items),
        usable_count=usable_count,
        purchase_history_notice=bool(customer and customer.email_verified_at is None),
        contact_email=_safe_optional_text(help_config.get("contact_email"), 320),
        contact_phone=_safe_optional_text(help_config.get("contact_phone"), 40),
        booking_url=_safe_booking_url(help_config.get("booking_url")),
        booking_instructions=_safe_optional_text(help_config.get("booking_instructions"), 1000),
    )


@router.post("/{voucher_id}/reorder")
async def reorder_account_voucher(
    voucher_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> dict[str, Any]:
    """Buy the exact original voucher variant again without copying gift details."""
    from sensoria.modules.accounts.router import _require_csrf

    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    await session.commit()
    cart, token, report = await reorder_voucher(
        session,
        customer_id=customer_id,
        voucher_id=voucher_id,
        cart_token=cart_token,
        idempotency_key=idempotency_key,
    )
    if cart.expires_at is None:
        raise DomainError("CART_EXPIRY_INVALID", "Nie można zapisać czasu ważności koszyka.", 500)
    _set_cart_cookie(response, token, cart.expires_at)
    response.delete_cookie(_COOKIE_NAME, path="/api", secure=True, httponly=True, samesite="lax")
    response.headers.update(PRIVATE_HEADERS)
    return {"report": report, "redirect": "/koszyk"}


async def _owned_voucher(
    session: AsyncSession,
    voucher_id: UUID,
    customer_id: UUID,
    *,
    for_update: bool = False,
) -> tuple[Voucher, Order]:
    statement = (
        select(Voucher, Order)
        .join(OrderItem, OrderItem.id == Voucher.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Voucher.id == voucher_id,
            Order.customer_id == customer_id,
        )
    )
    if for_update:
        statement = statement.with_for_update(of=Voucher)
    result = await session.execute(statement)
    row = result.one_or_none()
    if row is None:
        raise DomainError(
            "VOUCHER_NOT_FOUND",
            "Nie znaleziono vouchera.",
            404,
            headers=PRIVATE_HEADERS,
        )
    voucher, order = row
    return voucher, order


@router.get("/{voucher_id}/qr", response_class=Response)
async def voucher_qr(
    voucher_id: UUID,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> Response:
    """Generate an authenticated QR image for the owned voucher."""

    voucher, _order = await _owned_voucher(session, voucher_id, customer_id)
    target = f"{_setting_origin()}/voucher/{voucher.code}"
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=8, border=4)
    qr.add_data(target)
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    buffer = BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode("utf-8")
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )


@router.get("/{voucher_id}/pdf")
async def download_voucher_pdf(
    voucher_id: UUID,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> FileResponse:
    """Download the already rendered private PDF without exposing its path."""

    voucher, _order = await _owned_voucher(session, voucher_id, customer_id)
    if effective_voucher_status(voucher) not in {"active", "expiring_soon"}:
        raise DomainError(
            "VOUCHER_PDF_NOT_AVAILABLE",
            "Ten voucher nie jest już aktywny.",
            409,
            headers=PRIVATE_HEADERS,
        )
    if voucher.pdf_file_id is None:
        raise DomainError(
            "VOUCHER_PDF_PREPARING",
            "Dokument vouchera jest przygotowywany.",
            409,
            headers=PRIVATE_HEADERS,
        )
    stored_file = await session.get(StoredFile, voucher.pdf_file_id)
    if stored_file is None or stored_file.scope_id != voucher.id:
        raise DomainError(
            "VOUCHER_PDF_UNAVAILABLE",
            "Dokument vouchera jest niedostępny.",
            404,
            headers=PRIVATE_HEADERS,
        )
    path = StorageService().read_voucher_pdf(stored_file)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="voucher.pdf",
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )


@router.post("/{voucher_id}/extension-requests", status_code=201)
async def create_extension_request(
    voucher_id: UUID,
    payload: ExtensionRequestInput,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> dict[str, Any]:
    """Create a pending request; this endpoint never extends or reactivates a voucher."""

    voucher, order = await _owned_voucher(session, voucher_id, customer_id, for_update=True)
    status = effective_voucher_status(voucher)
    if status not in {"expired", "expiring_soon"}:
        raise DomainError(
            "VOUCHER_EXTENSION_REQUEST_NOT_ALLOWED",
            "Możesz poprosić o przedłużenie vouchera wygasającego lub wygasłego.",
            409,
            headers=PRIVATE_HEADERS,
        )
    now = datetime.now(UTC)
    existing = await session.scalar(
        select(VoucherExtensionRequest)
        .where(
            VoucherExtensionRequest.voucher_id == voucher.id,
            VoucherExtensionRequest.customer_id == customer_id,
            VoucherExtensionRequest.status == "pending",
        )
        .with_for_update()
    )
    if existing is not None:
        response.headers["Cache-Control"] = "private, no-store"
        return {"status": "pending", "request_id": str(existing.id), "duplicate": True}
    # Serialize per-customer throttling across API workers. This lock is transaction scoped;
    # only a hash collision can make unrelated accounts wait, never bypass the limit.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(0, hashtext(:customer_id))"),
        {"customer_id": str(customer_id)},
    )
    recent_count = await session.scalar(
        select(func.count())
        .select_from(VoucherExtensionRequest)
        .where(
            VoucherExtensionRequest.customer_id == customer_id,
            VoucherExtensionRequest.created_at >= now - timedelta(days=1),
        )
    )
    if (recent_count or 0) >= 3:
        oldest = await session.scalar(
            select(func.min(VoucherExtensionRequest.created_at)).where(
                VoucherExtensionRequest.customer_id == customer_id,
                VoucherExtensionRequest.created_at >= now - timedelta(days=1),
            )
        )
        retry_after = max(1, int(((oldest or now) + timedelta(days=1) - now).total_seconds()))
        raise DomainError(
            "VOUCHER_EXTENSION_RATE_LIMITED",
            "Wysłano już kilka próśb. Spróbuj ponownie po wskazanym czasie.",
            429,
            headers={**PRIVATE_HEADERS, "Retry-After": str(retry_after)},
        )
    request_record = VoucherExtensionRequest(
        voucher_id=voucher.id,
        order_id=order.id,
        customer_id=customer_id,
        message=payload.message.strip(),
    )
    session.add(request_record)
    session.add(
        AuditLog(
            actor_type=ActorType.CUSTOMER,
            actor_id=customer_id,
            entity_type="voucher",
            entity_id=voucher.id,
            action="extension_requested",
            payload={"request_id": str(request_record.id), "order_id": str(order.id)},
        )
    )
    await session.commit()
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {"status": "pending", "request_id": str(request_record.id), "duplicate": False}
