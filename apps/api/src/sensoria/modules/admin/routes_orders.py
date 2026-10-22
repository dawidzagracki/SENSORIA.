"""Order list/detail, internal notes, access resend and cancellation of unpaid orders."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select

from sensoria.config import get_settings
from sensoria.modules.admin.models import AdminUser, OrderNote
from sensoria.modules.documents.models import SalesDocument
from sensoria.modules.library.models import Entitlement
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.modules.orders.models import (
    DiscountUseReservation,
    Order,
    OrderItem,
    Shipment,
    StockReservation,
)
from sensoria.modules.payments.models import Payment
from sensoria.modules.payments.tokens import order_access_token
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .common import Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/orders", tags=["admin-orders"])
ORDER_STATUSES = "^(pending_payment|paid|cancelled|expired)$"
FULFILLMENT = "^(awaiting_fulfillment|shipped|delivered|ready_for_pickup|picked_up|cancelled)$"


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Notatka nie może być pusta.")
        return value


def _summary(order: Order, item_count: int) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "number": order.public_number,
        "created_at": order.created_at.isoformat(),
        "status": order.status,
        "fulfillment_status": order.fulfillment_status,
        "email": order.email,
        "amount_due_grosz": order.amount_due_grosz,
        "payment_method": order.payment_method,
        "item_count": item_count,
        "requires_shipping": isinstance(order.shipping_data, dict)
        and bool(order.shipping_data.get("method")),
    }


@router.get("")
async def list_orders(
    session: SessionDependency,
    _admin: Staff,
    status: Annotated[str | None, Query(pattern=ORDER_STATUSES)] = None,
    fulfillment: Annotated[str | None, Query(pattern=FULFILLMENT)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    statement = select(Order)
    if status:
        statement = statement.where(Order.status == status)
    if fulfillment:
        # Digital and voucher orders ship themselves; only physical ones need fulfilment.
        statement = statement.where(
            Order.fulfillment_status == fulfillment,
            Order.shipping_data["method"].astext.is_not(None),
        )
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Order.email).like(needle),
                func.lower(func.coalesce(Order.public_number, "")).like(needle),
            )
        )
    if date_from:
        statement = statement.where(
            Order.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to:
        statement = statement.where(
            Order.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    orders = list(
        (
            await session.scalars(
                statement.order_by(Order.created_at.desc(), Order.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
    )
    counts = dict(
        (
            await session.execute(
                select(OrderItem.order_id, func.count())
                .where(OrderItem.order_id.in_([o.id for o in orders]))
                .group_by(OrderItem.order_id)
            )
        )
        .tuples()
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_summary(o, int(counts.get(o.id, 0))) for o in orders],
    }


@router.get("/{order_id}")
async def order_detail(order_id: UUID, session: SessionDependency, admin: Staff) -> dict[str, Any]:
    order = await session.get(Order, order_id)
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
            )
        ).all()
    )
    payments = list(
        (
            await session.scalars(
                select(Payment).where(Payment.order_id == order_id).order_by(Payment.attempt)
            )
        ).all()
    )
    documents = list(
        (
            await session.scalars(select(SalesDocument).where(SalesDocument.order_id == order_id))
        ).all()
    )
    notes = (
        await session.execute(
            select(OrderNote, AdminUser.display_name)
            .outerjoin(AdminUser, AdminUser.id == OrderNote.admin_id)
            .where(OrderNote.order_id == order_id)
            .order_by(OrderNote.created_at)
        )
    ).all()
    mails = list(
        (
            await session.scalars(
                select(MailOutbox)
                .where(MailOutbox.order_id == order_id)
                .order_by(MailOutbox.created_at)
            )
        ).all()
    )
    shipment = await session.scalar(select(Shipment).where(Shipment.order_id == order_id))
    entitlements = int(
        await session.scalar(
            select(func.count()).select_from(Entitlement).where(Entitlement.order_id == order_id)
        )
        or 0
    )
    return {
        **_summary(order, len(items)),
        "invoice_data": order.invoice_data,
        "shipping_data": order.shipping_data,
        "delivery_point": order.delivery_point_snapshot,
        "calculation": order.calculation_snapshot,
        "items": [
            {
                "id": str(i.id),
                "name": i.product_name_snapshot,
                "quantity": i.quantity,
                "unit_price_grosz": i.unit_price_snapshot,
                "vat_rate": i.vat_rate_snapshot.value,
                "is_gift": i.gift_snapshot is not None,
            }
            for i in items
        ],
        "payments": [
            {
                "attempt": p.attempt,
                "status": p.status,
                "method": p.method,
                "amount_grosz": p.amount_grosz,
                "failure_code": p.failure_code,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in payments
        ],
        "documents": [{"id": str(d.id), "kind": d.kind, "number": d.number} for d in documents],
        "shipment": {
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "shipped_at": shipment.shipped_at.isoformat(),
        }
        if shipment
        else None,
        "notes": [
            {
                "id": str(n.id),
                "body": n.body,
                "author": author,
                "created_at": n.created_at.isoformat(),
            }
            for n, author in notes
        ],
        "mails": [
            {
                "template": m.template_key,
                "status": m.status,
                "attempts": m.attempts,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "last_error": m.last_error,
            }
            for m in mails
        ],
        "has_digital_access": entitlements > 0,
        "viewer_role": admin.role,
    }


@router.post("/{order_id}/notes", status_code=201)
async def add_note(
    order_id: UUID, payload: NoteInput, session: SessionDependency, admin: Staff
) -> dict[str, str]:
    async with session.begin():
        if await session.get(Order, order_id) is None:
            raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
        note = OrderNote(order_id=order_id, admin_id=admin.id, body=payload.body.strip())
        session.add(note)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="order",
                entity_id=order_id,
                action="order.note_added",
                payload={},
            )
        )
        await session.flush()
        return {"id": str(note.id)}


@router.post("/{order_id}/resend-access")
async def resend_access(
    order_id: UUID,
    session: SessionDependency,
    admin: Staff,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> dict[str, Any]:
    """Queue a fresh access mail (digital materials link); safe to retry with the same key."""
    async with session.begin():
        order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None:
            raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
        if order.status != "paid":
            raise DomainError("ORDER_NOT_PAID", "Zamówienie nie jest opłacone.", 409)
        titles = list(
            (
                await session.scalars(
                    select(OrderItem.product_name_snapshot)
                    .join(Entitlement, Entitlement.order_item_id == OrderItem.id)
                    .where(Entitlement.order_id == order_id, Entitlement.status == "active")
                )
            ).all()
        )
        if not titles:
            raise DomainError(
                "ORDER_NO_DIGITAL_ACCESS", "To zamówienie nie zawiera materiałów cyfrowych.", 409
            )
        origin = get_settings().SITE_URL or ""
        token = order_access_token(order.id)
        row = await enqueue_mail(
            session,
            template_key="digital_access",
            recipient=order.email,
            variables={
                "order_number": order.public_number or str(order.id),
                "titles": [t or "Materiał" for t in titles],
                "library_url": f"{origin}/zamowienie/potwierdzenie?order={order.id}&token={token}",
            },
            idempotency_key=f"resend-access:{order_id}:{idempotency_key}",
            order_id=order.id,
        )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="order",
                entity_id=order_id,
                action="order.access_resent",
                payload={"mail_id": str(row.id)},
            )
        )
        return {"mail_id": str(row.id), "status": row.status}


@router.post("/{order_id}/cancel")
async def cancel_unpaid(order_id: UUID, session: SessionDependency, admin: Staff) -> dict[str, str]:
    """Cancel an unpaid order and release its stock and discount holds."""
    async with session.begin():
        order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None:
            raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
        if order.status != "pending_payment":
            raise DomainError(
                "ORDER_NOT_CANCELLABLE",
                "Można anulować tylko zamówienie oczekujące na płatność.",
                409,
            )
        now = datetime.now(UTC)
        for hold in (
            await session.scalars(
                select(StockReservation)
                .where(
                    StockReservation.order_id == order_id, StockReservation.released_at.is_(None)
                )
                .with_for_update()
            )
        ).all():
            hold.released_at = now
        discount = await session.scalar(
            select(DiscountUseReservation)
            .where(DiscountUseReservation.order_id == order_id)
            .with_for_update()
        )
        if discount is not None:
            await session.delete(discount)
        order.status = "cancelled"
        order.fulfillment_status = "cancelled"
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="order",
                entity_id=order_id,
                action="order.cancelled",
                payload={},
            )
        )
    return {"status": "cancelled"}
