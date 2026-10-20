"""Eligibility rules (14-day withdrawal, 2-year complaints) and case creation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.modules.ops.alerts import notify_owner
from sensoria.modules.orders.models import Order, OrderConsent, OrderItem, Shipment
from sensoria.modules.reviews.service import clean_text
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import SupportCase

WITHDRAWAL_DAYS = 14
UNDELIVERED_GRACE_DAYS = 30
COMPLAINT_YEARS = 2
KIND_LABELS = {
    "withdrawal": "odstąpienie od umowy",
    "return": "zwrot towaru",
    "complaint": "reklamacja",
}


async def withdrawal_window_end(session: AsyncSession, order: Order) -> datetime:
    """14 days from receipt; undelivered parcels count from the order plus a delivery grace."""
    delivered_at = await session.scalar(
        select(Shipment.delivered_at).where(Shipment.order_id == order.id)
    )
    anchor = delivered_at or order.picked_up_at
    if anchor is None:
        anchor = order.created_at + timedelta(days=UNDELIVERED_GRACE_DAYS)
    return anchor + timedelta(days=WITHDRAWAL_DAYS)


async def _digital_waiver(session: AsyncSession, order: Order, item: OrderItem | None) -> bool:
    """True when immediate digital delivery with the recorded consent removes the right."""
    consent = await session.scalar(
        select(OrderConsent.granted).where(
            OrderConsent.order_id == order.id, OrderConsent.kind == "digital"
        )
    )
    if consent is not True:
        return False
    stmt = (
        select(func.count())
        .select_from(OrderItem)
        .join(Product, Product.id == OrderItem.product_id)
    )
    stmt = stmt.where(
        OrderItem.order_id == order.id,
        Product.kind.in_([ProductKind.DIGITAL, ProductKind.AUDIOBOOK]),
    )
    if item is not None:
        stmt = stmt.where(OrderItem.id == item.id)
    return int(await session.scalar(stmt) or 0) > 0


async def create_case(
    session: AsyncSession,
    *,
    order: Order,
    kind: str,
    order_item_id: UUID | None,
    message: str,
    now: datetime | None = None,
) -> SupportCase:
    moment = now or datetime.now(UTC)
    if order.status != "paid":
        raise DomainError(
            "SUPPORT_ORDER_NOT_PAID", "Zgłoszenie dotyczy opłaconego zamówienia.", 409
        )
    text = clean_text(message, multiline=True)
    if len(text) < 5 or len(text) > 3000:
        raise DomainError("SUPPORT_MESSAGE_INVALID", "Opis musi mieć od 5 do 3000 znaków.", 422)
    item: OrderItem | None = None
    if order_item_id is not None:
        item = await session.scalar(
            select(OrderItem).where(OrderItem.id == order_item_id, OrderItem.order_id == order.id)
        )
        if item is None:
            raise DomainError("SUPPORT_ITEM_NOT_FOUND", "Nie znaleziono pozycji zamówienia.", 404)
    if kind in {"withdrawal", "return"}:
        if await _digital_waiver(session, order, item):
            raise DomainError(
                "WITHDRAWAL_DIGITAL_WAIVED",
                "Przy treściach cyfrowych udostępnionych od razu wyraziłaś zgodę na rozpoczęcie "
                "świadczenia i utratę prawa odstąpienia. Jeśli jest problem z plikiem, "
                "złóż reklamację.",
                409,
            )
        if moment > await withdrawal_window_end(session, order):
            raise DomainError(
                "WITHDRAWAL_WINDOW_CLOSED",
                "Minął 14-dniowy termin na odstąpienie od umowy.",
                409,
            )
        if kind == "return" and order.shipping_data is None:
            raise DomainError(
                "RETURN_NOT_PHYSICAL", "Zwrot towaru dotyczy wyłącznie przesyłek fizycznych.", 409
            )
    elif kind == "complaint":
        if moment > order.created_at + timedelta(days=365 * COMPLAINT_YEARS):
            raise DomainError(
                "COMPLAINT_WINDOW_CLOSED", "Minął okres odpowiedzialności za zgodność towaru.", 409
            )
    else:
        raise DomainError("SUPPORT_KIND_INVALID", "Nieznany rodzaj zgłoszenia.", 422)
    case = SupportCase(
        public_number=f"ZG-{moment.year}-{uuid4().hex[:8].upper()}",
        kind=kind,
        order_id=order.id,
        order_item_id=order_item_id,
        email=order.email,
        message=text,
    )
    session.add(case)
    await session.flush()
    session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            entity_type="support_case",
            entity_id=case.id,
            action="support.created",
            payload={"kind": kind, "order_id": str(order.id)},
        )
    )
    await enqueue_mail(
        session,
        template_key="support_confirmation",
        recipient=order.email,
        variables={
            "case_number": case.public_number,
            "kind_label": KIND_LABELS[kind],
            "summary": text[:400],
        },
        idempotency_key=f"support-confirmation:{case.id}",
        order_id=order.id,
    )
    await notify_owner(
        session,
        key=f"support:{case.id}",
        title=f"Nowe zgłoszenie: {KIND_LABELS[kind]}",
        lines=[f"Numer: {case.public_number}", f"Zamówienie: {order.public_number}"],
    )
    return case
