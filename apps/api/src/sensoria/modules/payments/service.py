"""Payment orchestration: session start, trusted webhook processing and order status."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import Settings
from sensoria.modules.catalog.inventory import record_paid_order_inventory
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.orders.service import record_paid_discount_use
from sensoria.modules.orders.shipments import mark_fulfillment_ready_after_payment
from sensoria.modules.vouchers.service import issue_vouchers_for_paid_order
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import Payment, PaymentEvent
from .stripe_client import create_checkout_session, stripe_configured
from .tokens import verify_order_access_token

logger = logging.getLogger("sensoria.payments")

METHODS = {"blik": ["blik"], "card": ["card"], "wallet": ["card"]}
SUCCESS_EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
FAILURE_EVENTS = {"checkout.session.async_payment_failed"}
EXPIRY_EVENTS = {"checkout.session.expired"}


def _authorized_order_query(order_id: UUID, token: str) -> None:
    if not verify_order_access_token(order_id, token):
        # Same response as a missing order so identifiers cannot be probed.
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)


async def start_payment(
    session: AsyncSession, settings: Settings, *, order_id: UUID, token: str, site_url: str
) -> Payment:
    """Return the live hosted session for a pending order, creating a new attempt if needed."""
    _authorized_order_query(order_id, token)
    if not stripe_configured(settings):
        raise DomainError(
            "PAYMENT_NOT_CONFIGURED", "Płatności online nie są jeszcze skonfigurowane.", 503
        )
    async with session.begin():
        order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None:
            raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
        if order.status == "paid":
            raise DomainError("ORDER_ALREADY_PAID", "To zamówienie jest już opłacone.", 409)
        if order.status != "pending_payment":
            raise DomainError("ORDER_NOT_PAYABLE", "Zamówienie wygasło lub zostało anulowane.", 409)
        if order.amount_due_grosz <= 0:
            raise DomainError("ORDER_NOTHING_TO_PAY", "Zamówienie nie wymaga płatności.", 409)
        attempts = list(
            (
                await session.scalars(
                    select(Payment).where(Payment.order_id == order_id).order_by(Payment.attempt)
                )
            ).all()
        )
        now = datetime.now(UTC)
        pending = next((p for p in attempts if p.status == "pending"), None)
        if (
            pending is not None
            and pending.checkout_url
            and pending.session_expires_at is not None
            and pending.session_expires_at > now
        ):
            return pending
        if pending is not None:
            pending.status = "expired"
            await session.flush()
        attempt_number = (attempts[-1].attempt + 1) if attempts else 1
        created = await create_checkout_session(
            settings,
            order_id=str(order.id),
            order_number=order.public_number or str(order.id),
            email=order.email,
            amount_grosz=order.amount_due_grosz,
            methods=METHODS.get(order.payment_method, ["card"]),
            success_url=(f"{site_url}/zamowienie/potwierdzenie?order={order.id}&token={token}"),
            cancel_url=f"{site_url}/zamowienie/potwierdzenie?order={order.id}&token={token}",
            attempt=attempt_number,
        )
        payment = Payment(
            order_id=order.id,
            provider="stripe",
            provider_session_id=created.session_id,
            provider_payment_intent_id=created.payment_intent_id,
            checkout_url=created.url,
            method=order.payment_method,
            amount_grosz=order.amount_due_grosz,
            currency="PLN",
            attempt=attempt_number,
            session_expires_at=datetime.fromtimestamp(created.expires_at, UTC),
        )
        session.add(payment)
        await session.flush()
        return payment


async def _confirm_paid(session: AsyncSession, order: Order, payment: Payment) -> None:
    """Run every payment-confirmed side effect inside the caller's transaction."""
    paid_at = datetime.now(UTC)
    payment.status = "succeeded"
    payment.paid_at = paid_at
    order.status = "paid"
    await session.flush()
    if order.discount_code_id is not None:
        await record_paid_discount_use(
            session, discount_code_id=order.discount_code_id, order_id=order.id
        )
    await record_paid_order_inventory(session, order.id, confirmed_at=paid_at)
    await issue_vouchers_for_paid_order(session, order.id, now=paid_at)
    await mark_fulfillment_ready_after_payment(session, order_id=order.id, paid_at=paid_at)
    session.add(
        AuditLog(
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            entity_type="order",
            entity_id=order.id,
            action="order.payment.confirmed",
            payload={"payment_id": str(payment.id), "amount_grosz": payment.amount_grosz},
        )
    )
    await session.flush()


def _session_object(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    return obj if isinstance(obj, dict) else {}


async def process_event(session: AsyncSession, event: dict[str, Any]) -> str:
    """Apply one verified provider event exactly once and return its outcome."""
    event_id = str(event["id"])
    event_type = str(event.get("type", ""))
    async with session.begin():
        inserted = await session.scalar(
            pg_insert(PaymentEvent)
            .values(
                provider="stripe",
                provider_event_id=event_id,
                event_type=event_type[:100],
                outcome="processing",
                summary={},
            )
            .on_conflict_do_nothing(index_elements=["provider", "provider_event_id"])
            .returning(PaymentEvent.id)
        )
        if inserted is None:
            return "duplicate"
        ledger = await session.get(PaymentEvent, inserted)
        assert ledger is not None
        relevant = event_type in SUCCESS_EVENTS | FAILURE_EVENTS | EXPIRY_EVENTS
        if not relevant:
            ledger.outcome = "ignored"
            return "ignored"
        obj = _session_object(event)
        session_id = obj.get("id")
        payment = (
            await session.scalar(
                select(Payment)
                .where(Payment.provider_session_id == str(session_id))
                .with_for_update()
            )
            if isinstance(session_id, str)
            else None
        )
        if payment is None:
            ledger.outcome = "unknown_session"
            logger.warning("Zdarzenie płatności dla nieznanej sesji [%s].", event_type)
            return "unknown_session"
        ledger.payment_id = payment.id
        order = await session.scalar(
            select(Order).where(Order.id == payment.order_id).with_for_update()
        )
        assert order is not None
        intent = obj.get("payment_intent")
        if isinstance(intent, str):
            payment.provider_payment_intent_id = intent
        if event_type in SUCCESS_EVENTS:
            if obj.get("payment_status") != "paid":
                ledger.outcome = "awaiting_async_payment"
                return ledger.outcome
            if payment.status == "succeeded" or order.status == "paid":
                ledger.outcome = "already_paid"
                return ledger.outcome
            amount_ok = obj.get("amount_total") == order.amount_due_grosz
            currency_ok = str(obj.get("currency", "")).lower() == "pln"
            if not (amount_ok and currency_ok):
                payment.status = "amount_mismatch"
                payment.failure_code = "amount_mismatch"
                session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        actor_id=None,
                        entity_type="payment",
                        entity_id=payment.id,
                        action="payment.amount_mismatch",
                        payload={"order_id": str(order.id)},
                    )
                )
                ledger.outcome = "amount_mismatch"
                return ledger.outcome
            await _confirm_paid(session, order, payment)
            ledger.outcome = "paid"
            return ledger.outcome
        if payment.status == "pending":
            payment.status = "failed" if event_type in FAILURE_EVENTS else "expired"
            payment.failure_code = "async_payment_failed" if event_type in FAILURE_EVENTS else None
            session.add(
                AuditLog(
                    actor_type=ActorType.SYSTEM,
                    actor_id=None,
                    entity_type="payment",
                    entity_id=payment.id,
                    action=f"payment.{payment.status}",
                    payload={"order_id": str(order.id), "attempt": payment.attempt},
                )
            )
        ledger.outcome = payment.status
        return ledger.outcome


async def order_status_view(session: AsyncSession, *, order_id: UUID, token: str) -> dict[str, Any]:
    """Public confirmation payload; contains no card data and no other buyers' information."""
    _authorized_order_query(order_id, token)
    order = await session.scalar(select(Order).where(Order.id == order_id))
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    latest = await session.scalar(
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.attempt.desc())
        .limit(1)
    )
    items = list(
        (
            await session.scalars(
                select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
            )
        ).all()
    )
    local, _, domain = order.email.partition("@")
    masked = f"{local[:1]}***@{domain}"
    shipping = order.shipping_data or {}
    return {
        "order_id": order.id,
        "public_number": order.public_number,
        "status": order.status,
        "payment_status": latest.status if latest else None,
        "payment_method": order.payment_method,
        "amount_due_grosz": order.amount_due_grosz,
        "email_masked": masked,
        "created_at": order.created_at,
        "requires_shipping": bool(shipping),
        "delivery_method": shipping.get("method"),
        "items": [
            {
                "name": item.product_name_snapshot,
                "quantity": item.quantity,
                "unit_price_grosz": item.unit_price_snapshot,
                "is_voucher": item.voucher_snapshot is not None,
            }
            for item in items
        ],
        "can_retry_payment": order.status == "pending_payment"
        and (latest is None or latest.status in {"failed", "expired", "pending"}),
        "server_time": datetime.now(UTC),
    }
