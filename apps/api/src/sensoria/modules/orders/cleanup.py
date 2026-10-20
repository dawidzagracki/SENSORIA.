"""Bounded, concurrency-safe cleanup of expired guest carts."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import Settings, get_settings
from sensoria.database import SessionFactory
from sensoria.modules.accounts.mail_jobs import cleanup_login_link_payloads
from sensoria.modules.catalog.models import ProductBook

from .models import Cart, DiscountUseReservation, Order, StockReservation

logger = logging.getLogger("sensoria.orders.cart_cleanup")


async def delete_expired_guest_carts(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int | None = None,
) -> int:
    """Delete up to one batch; locked carts are skipped during account merge."""

    size = batch_size if batch_size is not None else get_settings().CART_CLEANUP_BATCH_SIZE
    if size < 1:
        raise ValueError("batch_size musi być dodatnie.")
    async with session_factory() as session, session.begin():
        ids = list(
            (
                await session.scalars(
                    select(Cart.id)
                    .where(Cart.customer_id.is_(None), Cart.expires_at <= func.now())
                    .order_by(Cart.expires_at, Cart.id)
                    .limit(size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if not ids:
            return 0
        await session.execute(delete(Cart).where(Cart.id.in_(ids)))
        return len(ids)


async def expire_stock_reservations(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    batch_size: int = 100,
) -> int:
    """Expire 24-hour pending orders, releasing holds without physical stock movement."""
    if batch_size < 1:
        raise ValueError("batch_size musi być dodatnie.")
    async with session_factory() as session, session.begin():
        orders = list(
            (
                await session.scalars(
                    select(Order)
                    .where(
                        Order.status == "pending_payment",
                        Order.created_at <= func.now() - text("interval '24 hours'"),
                    )
                    .order_by(Order.created_at, Order.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        released_count = 0
        for order in orders:
            product_ids = sorted(
                set(
                    (
                        await session.scalars(
                            select(StockReservation.product_id).where(
                                StockReservation.order_id == order.id,
                                StockReservation.released_at.is_(None),
                            )
                        )
                    ).all()
                )
            )
            for product_id in product_ids:
                await session.scalar(
                    select(ProductBook)
                    .where(ProductBook.product_id == product_id)
                    .with_for_update()
                )
            reservations = list(
                (
                    await session.scalars(
                        select(StockReservation)
                        .where(
                            StockReservation.order_id == order.id,
                            StockReservation.released_at.is_(None),
                        )
                        .order_by(StockReservation.product_id, StockReservation.id)
                        .with_for_update()
                    )
                ).all()
            )
            active = await session.scalar(
                select(StockReservation.id)
                .where(
                    StockReservation.order_id == order.id,
                    StockReservation.released_at.is_(None),
                    StockReservation.expires_at > func.now(),
                )
                .limit(1)
            )
            if active is not None:
                continue
            for reservation in reservations:
                reservation.released_at = func.now()
                released_count += 1
            order.status = "expired"
            hold = await session.scalar(
                select(DiscountUseReservation)
                .where(DiscountUseReservation.order_id == order.id)
                .with_for_update()
            )
            if hold is not None:
                await session.delete(hold)
        return released_count


async def cleanup_scheduler(settings: Settings | None = None) -> None:
    """Run periodically in each API worker; SKIP LOCKED coordinates concurrent workers."""

    selected = settings or get_settings()
    while True:
        await asyncio.sleep(selected.CART_CLEANUP_INTERVAL_SECONDS)
        try:
            await delete_expired_guest_carts(batch_size=selected.CART_CLEANUP_BATCH_SIZE)
            await expire_stock_reservations(batch_size=selected.CART_CLEANUP_BATCH_SIZE)
            await cleanup_login_link_payloads(batch_size=selected.CART_CLEANUP_BATCH_SIZE)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Avoid logging database exception text, which can include query parameters.
            logger.error("Czyszczenie koszyków nie powiodło się [%s].", type(error).__name__)


async def _run_once() -> None:
    deleted = await delete_expired_guest_carts()
    logger.info("Usunięto wygasłe koszyki gości: %s.", deleted)


if __name__ == "__main__":
    asyncio.run(_run_once())
