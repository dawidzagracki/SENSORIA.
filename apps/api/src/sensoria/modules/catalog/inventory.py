"""Transactional stock ledger operations and checkout settlement integration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.orders.models import (
    Order,
    OrderItem,
    StockFulfillmentConflict,
    StockReservation,
)
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import LowStockAlert, Product, ProductBook, StockMovement
from .types import ProductKind


def is_low_stock_crossing(previous: int, current: int, threshold: int) -> bool:
    """Return true only when physical stock crosses below its configured threshold."""

    if min(previous, current, threshold) < 0:
        raise ValueError("Stan i próg muszą być nieujemne.")
    return threshold > 0 and previous >= threshold and current < threshold


async def current_book_inventory(
    session: AsyncSession, product_ids: set[UUID]
) -> dict[UUID, tuple[int, int]]:
    """Return live (physical, available) book counts for public catalog presentation."""

    if not product_ids:
        return {}
    reserved = (
        select(func.coalesce(func.sum(StockReservation.quantity), 0))
        .join(Order, Order.id == StockReservation.order_id)
        .where(
            StockReservation.product_id == ProductBook.product_id,
            StockReservation.released_at.is_(None),
            StockReservation.expires_at > func.now(),
            Order.status == "pending_payment",
        )
        .correlate(ProductBook)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(ProductBook.product_id, ProductBook.stock_quantity, reserved).where(
            ProductBook.product_id.in_(product_ids)
        )
    )
    result: dict[UUID, tuple[int, int]] = {}
    for product_id, physical, reserved_quantity in rows:
        physical_quantity = int(physical)
        available = max(0, physical_quantity - int(reserved_quantity or 0))
        result[product_id] = (physical_quantity, available)
    return result


def available_quantity(stock_quantity: int, reserved_quantity: int) -> int:
    """Return physical units that are not held for pending orders."""

    if (
        isinstance(stock_quantity, bool)
        or not isinstance(stock_quantity, int)
        or stock_quantity < 0
        or isinstance(reserved_quantity, bool)
        or not isinstance(reserved_quantity, int)
        or reserved_quantity < 0
    ):
        raise ValueError("Stan i rezerwacje muszą być nieujemnymi liczbami całkowitymi.")
    if reserved_quantity > stock_quantity:
        raise ValueError("Aktywne rezerwacje nie mogą przekraczać stanu fizycznego.")
    return stock_quantity - reserved_quantity


def calculate_shipment_weight(lines: list[tuple[int, int]]) -> int:
    """Sum weights in grams for physical order lines only."""

    total = 0
    for weight_grams, quantity in lines:
        if (
            isinstance(weight_grams, bool)
            or not isinstance(weight_grams, int)
            or weight_grams <= 0
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            raise ValueError("Waga i ilość muszą być dodatnimi liczbami całkowitymi.")
        total += weight_grams * quantity
    return total


async def append_stock_movement(
    session: AsyncSession,
    *,
    product_id: UUID,
    change: int,
    reason: str,
    operation_key: str,
    actor_id: UUID | None,
    actor_type: ActorType,
    order_id: UUID | None = None,
    order_item_id: UUID | None = None,
    source_reference: str | None = None,
    note: str | None = None,
) -> StockMovement:
    """Append one movement in the caller's transaction; the DB trigger updates stock."""

    if isinstance(change, bool) or not isinstance(change, int) or change == 0:
        raise DomainError(
            "STOCK_CHANGE_INVALID", "Zmiana stanu musi być niezerową liczbą całkowitą.", 422
        )
    if reason not in {"purchase", "return", "manual_adjustment", "correction"}:
        raise DomainError("STOCK_REASON_INVALID", "Nieznany powód zmiany stanu.", 422)
    if reason == "manual_adjustment" and (actor_id is None or not note or not note.strip()):
        raise DomainError(
            "STOCK_ADJUSTMENT_REASON_REQUIRED", "Korekta wymaga administratora i uzasadnienia.", 422
        )
    if reason == "manual_adjustment" and actor_type is not ActorType.ADMINISTRATOR:
        raise DomainError(
            "STOCK_ADJUSTMENT_ADMIN_REQUIRED", "Korektę może wykonać wyłącznie administracja.", 403
        )
    if len(operation_key) > 160 or not operation_key.strip():
        raise DomainError(
            "STOCK_OPERATION_KEY_INVALID",
            "Identyfikator operacji jest nieprawidłowy.",
            422,
        )

    book = await session.scalar(
        select(ProductBook).where(ProductBook.product_id == product_id).with_for_update()
    )
    if book is None:
        raise DomainError("STOCK_PRODUCT_NOT_FOUND", "Nie znaleziono książki w magazynie.", 404)
    existing = await session.scalar(
        select(StockMovement).where(StockMovement.operation_key == operation_key)
    )
    if existing is not None:
        if (
            existing.product_id != product_id
            or existing.change != change
            or existing.reason != reason
            or existing.order_id != order_id
            or existing.order_item_id != order_item_id
        ):
            raise DomainError(
                "STOCK_IDEMPOTENCY_CONFLICT",
                "Klucz operacji został już użyty dla innego ruchu magazynowego.",
                409,
            )
        return existing

    previous = book.stock_quantity
    threshold = book.low_stock_threshold
    if change < 0:
        reserved = int(
            await session.scalar(
                select(func.coalesce(func.sum(StockReservation.quantity), 0))
                .join(Order, Order.id == StockReservation.order_id)
                .where(
                    StockReservation.product_id == product_id,
                    StockReservation.released_at.is_(None),
                    StockReservation.expires_at > func.now(),
                    Order.status == "pending_payment",
                )
            )
            or 0
        )
        if previous + change < reserved:
            raise DomainError(
                "STOCK_BELOW_RESERVATIONS",
                "Zmiana pozostawiłaby mniej egzemplarzy niż aktywne rezerwacje.",
                409,
            )

    movement = StockMovement(
        product_id=product_id,
        change=change,
        reason=reason,
        order_id=order_id,
        order_item_id=order_item_id,
        source_reference=source_reference,
        operation_key=operation_key,
        performed_by=actor_id,
        note=note.strip() if note else None,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(book, attribute_names=["stock_quantity"])
    if is_low_stock_crossing(previous, book.stock_quantity, threshold):
        session.add(
            LowStockAlert(
                product_id=product_id,
                movement_id=movement.id,
                previous_stock=previous,
                current_stock=book.stock_quantity,
            )
        )
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            entity_type="stock_movement",
            entity_id=movement.id,
            action="stock.movement.recorded",
            payload={
                "product_id": str(product_id),
                "order_id": str(order_id) if order_id else None,
                "order_item_id": str(order_item_id) if order_item_id else None,
                "change": change,
                "reason": reason,
                "previous_stock": previous,
                "new_stock": book.stock_quantity,
                "operation_key": operation_key,
            },
        )
    )
    return movement


async def record_paid_order_inventory(
    session: AsyncSession, order_id: UUID, *, confirmed_at: datetime | None = None
) -> list[UUID]:
    """Consume physical items after trusted payment, within the webhook transaction.

    The caller must have confirmed and locked the order as paid in this same transaction.
    Returns item IDs with an explicit fulfillment conflict; it never invents stock.
    """

    if confirmed_at is not None and (
        confirmed_at.tzinfo is None or confirmed_at.utcoffset() is None
    ):
        raise ValueError("Czas potwierdzenia płatności musi zawierać strefę.")
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.status != "paid":
        raise DomainError(
            "STOCK_ORDER_NOT_PAID",
            "Stan magazynu można rozliczyć po płatności.",
            409,
        )
    rows = list(
        (
            await session.execute(
                select(OrderItem, Product)
                .join(Product, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id == order_id, Product.kind == ProductKind.BOOK)
                .order_by(Product.id, OrderItem.id)
            )
        ).all()
    )
    conflicts: list[UUID] = []
    for item, product in rows:
        book = await session.scalar(
            select(ProductBook).where(ProductBook.product_id == product.id).with_for_update()
        )
        if book is None:
            raise DomainError("STOCK_BOOK_DETAILS_MISSING", "Brakuje danych książki.", 409)
        key = f"purchase:{item.id}"
        existing = await session.scalar(
            select(StockMovement.id).where(StockMovement.operation_key == key)
        )
        holds = list(
            (
                await session.scalars(
                    select(StockReservation)
                    .where(
                        StockReservation.order_id == order_id,
                        StockReservation.product_id == product.id,
                        StockReservation.released_at.is_(None),
                        or_(
                            StockReservation.order_item_id.is_(None),
                            StockReservation.order_item_id == item.id,
                        ),
                    )
                    .order_by(StockReservation.id)
                    .with_for_update()
                )
            ).all()
        )
        if existing is not None:
            for hold in holds:
                hold.released_at = confirmed_at or datetime.now(UTC)
            conflict = await session.scalar(
                select(StockFulfillmentConflict)
                .where(StockFulfillmentConflict.order_item_id == item.id)
                .with_for_update()
            )
            if conflict is not None:
                conflict.status = "resolved"
            continue

        now = confirmed_at.astimezone(UTC) if confirmed_at else datetime.now(UTC)
        active_own = sum(hold.quantity for hold in holds if hold.expires_at.astimezone(UTC) > now)
        other_reserved = int(
            await session.scalar(
                select(func.coalesce(func.sum(StockReservation.quantity), 0))
                .join(Order, Order.id == StockReservation.order_id)
                .where(
                    StockReservation.product_id == product.id,
                    StockReservation.order_id != order_id,
                    StockReservation.released_at.is_(None),
                    StockReservation.expires_at > func.now(),
                    Order.status == "pending_payment",
                )
            )
            or 0
        )
        if active_own < item.quantity and book.stock_quantity - other_reserved < item.quantity:
            conflict = await session.scalar(
                select(StockFulfillmentConflict)
                .where(StockFulfillmentConflict.order_item_id == item.id)
                .with_for_update()
            )
            if conflict is None:
                conflict = StockFulfillmentConflict(
                    order_id=order_id,
                    order_item_id=item.id,
                    product_id=product.id,
                    requested_quantity=item.quantity,
                )
                session.add(conflict)
                await session.flush()
                session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        actor_id=None,
                        entity_type="stock_fulfillment_conflict",
                        entity_id=conflict.id,
                        action="stock.fulfillment.conflict",
                        payload={
                            "order_id": str(order_id),
                            "order_item_id": str(item.id),
                            "product_id": str(product.id),
                            "requested_quantity": item.quantity,
                            "reason": "payment_arrived_after_hold_expired",
                        },
                    )
                )
            conflicts.append(item.id)
            continue

        for hold in holds:
            hold.released_at = now
        await session.flush()
        await append_stock_movement(
            session,
            product_id=product.id,
            change=-item.quantity,
            reason="purchase",
            operation_key=key,
            actor_id=None,
            actor_type=ActorType.SYSTEM,
            order_id=order_id,
            order_item_id=item.id,
            note="Rozliczenie opłaconego zamówienia.",
        )
        conflict = await session.scalar(
            select(StockFulfillmentConflict)
            .where(StockFulfillmentConflict.order_item_id == item.id)
            .with_for_update()
        )
        if conflict is not None:
            conflict.status = "resolved"
    return conflicts
