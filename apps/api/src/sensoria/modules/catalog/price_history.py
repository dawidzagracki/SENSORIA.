"""Append-only product price snapshots, audit events, and historical lookup."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    event,
    func,
    inspect,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from sensoria.database import Base, UUIDMixin
from sensoria.shared.audit_log import ActorType, ActorTypeType, AuditLog
from sensoria.shared.types import Money, VatRate, VatRateType

from .models import Product

_CONTEXT_KEY = "sensoria_price_change_context"
_GUARD_KEY = "sensoria_price_write_guard_enabled"
_PRICE_FIELDS = ("price", "compare_at_price", "vat_rate")


@dataclass(frozen=True, slots=True)
class PriceChangeContext:
    """Per-session operation attribution; never shared between requests."""

    actor_type: ActorType
    actor_id: UUID | None
    reason: str


class PriceHistory(UUIDMixin, Base):
    """Immutable price snapshot. ``version`` resolves identical DB timestamps."""

    __tablename__ = "price_history"
    __table_args__ = (
        CheckConstraint("price IS NULL OR price >= 0", name="nonnegative_price"),
        CheckConstraint(
            "compare_at_price IS NULL OR (price IS NOT NULL AND compare_at_price > price)",
            name="compare_above_price",
        ),
        CheckConstraint(
            "vat_rate IS NULL OR vat_rate IN ('RATE_23', 'RATE_8', 'RATE_5', 'RATE_0', 'EXEMPT')",
            name="valid_vat_rate",
        ),
        CheckConstraint(
            "actor_type IN ('customer', 'administrator', 'system')", name="valid_actor_type"
        ),
        CheckConstraint("length(btrim(reason)) > 0", name="nonempty_reason"),
        Index("ix_price_history_product_valid_from", "product_id", "valid_from", "version"),
        Index("ix_price_history_product_version", "product_id", "version"),
    )

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    price: Mapped[int | None] = mapped_column(Money(), nullable=True)
    compare_at_price: Mapped[int | None] = mapped_column(Money(), nullable=True)
    vat_rate: Mapped[VatRate | None] = mapped_column(VatRateType(), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    changed_by: Mapped[UUID | None] = mapped_column(nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(ActorTypeType(), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    product: Mapped[Product] = relationship(lazy="raise")


@asynccontextmanager
async def price_change_context(
    session: AsyncSession,
    *,
    actor_type: ActorType,
    actor_id: UUID | None,
    reason: str,
) -> AsyncIterator[None]:
    """Attribute ORM price mutations to this operation and restore prior context."""

    clean_reason = reason.strip()
    if not clean_reason or len(clean_reason) > 500:
        raise ValueError("Powód zmiany ceny musi mieć od 1 do 500 znaków.")
    if not isinstance(actor_type, ActorType):
        raise TypeError("Typ autora musi być wartością ActorType.")
    previous = session.info.get(_CONTEXT_KEY)
    session.info[_CONTEXT_KEY] = PriceChangeContext(actor_type, actor_id, clean_reason)
    try:
        yield
    finally:
        if previous is None:
            session.info.pop(_CONTEXT_KEY, None)
        else:
            session.info[_CONTEXT_KEY] = previous


async def lowest_price_last_30_days(
    session: AsyncSession,
    product_id: UUID,
    at: datetime,
) -> int | None:
    """Return minimum effective gross price during ``[at - 30d, at)``.

    The snapshot effective at the interval start is included, even when it was
    recorded earlier. ``at`` must be timezone-aware and is normalized to UTC.
    """

    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Moment odniesienia musi zawierać strefę czasową.")
    end = at.astimezone(UTC)
    start = end - timedelta(days=30)
    opening_price = await session.scalar(
        select(PriceHistory.price)
        .where(PriceHistory.product_id == product_id, PriceHistory.valid_from <= start)
        .order_by(PriceHistory.valid_from.desc(), PriceHistory.version.desc())
        .limit(1)
    )
    window_minimum = await session.scalar(
        select(func.min(PriceHistory.price)).where(
            PriceHistory.product_id == product_id,
            PriceHistory.valid_from > start,
            PriceHistory.valid_from < end,
        )
    )
    candidates = [price for price in (opening_price, window_minimum) if price is not None]
    return min(candidates) if candidates else None


async def lowest_price_before_current_discount(
    session: AsyncSession,
    product_id: UUID,
    *,
    price: int,
    compare_at_price: int | None,
) -> tuple[int | None, datetime | None]:
    """Return the 30-day minimum and start of the current recorded sale.

    A sale start is the first snapshot in the latest uninterrupted run with
    the current ``price`` and ``compare_at_price``. VAT-only snapshots do not
    split that run. If history has no preceding, different price state, the
    start cannot be established and the result is explicitly unknown.
    """

    if compare_at_price is None or compare_at_price <= price:
        return None, None

    latest_version = await session.scalar(
        select(PriceHistory.version)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.valid_from.desc(), PriceHistory.version.desc())
        .limit(1)
    )
    if latest_version is None:
        return None, None

    previous_state_version = await session.scalar(
        select(PriceHistory.version)
        .where(
            PriceHistory.product_id == product_id,
            PriceHistory.version < latest_version,
            (PriceHistory.price.is_distinct_from(price))
            | (PriceHistory.compare_at_price.is_distinct_from(compare_at_price)),
        )
        .order_by(PriceHistory.version.desc())
        .limit(1)
    )
    if previous_state_version is None:
        return None, None

    sale_started_at = await session.scalar(
        select(PriceHistory.valid_from)
        .where(
            PriceHistory.product_id == product_id,
            PriceHistory.version > previous_state_version,
            PriceHistory.price == price,
            PriceHistory.compare_at_price == compare_at_price,
        )
        .order_by(PriceHistory.version.asc())
        .limit(1)
    )
    if sale_started_at is None:
        return None, None

    lowest_price = await lowest_price_last_30_days(session, product_id, sale_started_at)
    return lowest_price, sale_started_at


def _price_values(product: Product) -> dict[str, int | str | None]:
    rate = product.vat_rate
    return {
        "price": product.price,
        "compare_at_price": product.compare_at_price,
        "vat_rate": rate.value if rate is not None else None,
    }


def _validate_price_relation(product: Product) -> None:
    if product.compare_at_price is not None and (
        product.price is None or product.compare_at_price <= product.price
    ):
        raise ValueError("Cena porównawcza musi być wyższa od ceny produktu.")


def _before_flush(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances
    candidates: list[tuple[Product, bool, dict[str, int | str | None] | None]] = []
    for product in tuple(session.new) + tuple(session.dirty):
        if not isinstance(product, Product):
            continue
        is_new = product in session.new
        old: dict[str, int | str | None] | None = None
        if not is_new:
            if not session.is_modified(product, include_collections=False):
                continue
            inspected = inspect(product)
            if not any(inspected.attrs[field].history.has_changes() for field in _PRICE_FIELDS):
                continue
            old = {}
            for field in _PRICE_FIELDS:
                history = inspected.attrs[field].history
                value = history.deleted[0] if history.deleted else getattr(product, field)
                old[field] = value.value if isinstance(value, VatRate) else value
            if old == _price_values(product):
                continue
        else:
            old = None
        _validate_price_relation(product)
        candidates.append((product, is_new, old))

    if not candidates:
        return

    for product, is_new, _old in candidates:
        if is_new and getattr(product, "id", None) is None:
            product.id = uuid4()

    connection = session.connection()
    connection.exec_driver_sql("SELECT set_config('sensoria.price_write_guard', 'on', true)")
    session.info[_GUARD_KEY] = True
    context = cast(
        PriceChangeContext | None,
        session.info.get(_CONTEXT_KEY),
    )
    for product, is_new, old in candidates:
        current = _price_values(product)
        actor_type = context.actor_type if context else ActorType.SYSTEM
        actor_id = context.actor_id if context else None
        reason = (
            context.reason
            if context
            else ("Początkowy zapis produktu" if is_new else "Systemowa aktualizacja cen")
        )
        session.add(
            PriceHistory(
                product=product,
                price=product.price,
                compare_at_price=product.compare_at_price,
                vat_rate=product.vat_rate,
                changed_by=actor_id,
                actor_type=actor_type,
                reason=reason,
            )
        )
        session.add(
            AuditLog(
                actor_type=actor_type,
                actor_id=actor_id,
                entity_type="product",
                entity_id=product.id,
                action="product.price.initialized" if is_new else "product.price.changed",
                payload={
                    "reason": reason,
                    "previous": old,
                    "current": current,
                },
            )
        )


def _after_flush_postexec(session: Session, flush_context: object) -> None:
    del flush_context
    if session.info.pop(_GUARD_KEY, False):
        session.connection().exec_driver_sql(
            "SELECT set_config('sensoria.price_write_guard', 'off', true)"
        )


def _reject_history_mutation(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances
    if any(
        isinstance(entry, PriceHistory) for entry in tuple(session.dirty) + tuple(session.deleted)
    ):
        raise ValueError("Historia cen jest dopisywana i nie może być zmieniana ani usuwana.")


def register_price_history_events(product_type: type[Product]) -> None:
    """Register ORM hooks once the catalog Product mapping exists."""

    del product_type
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush_postexec", _after_flush_postexec)
    event.listen(Session, "before_flush", _reject_history_mutation, insert=True)
