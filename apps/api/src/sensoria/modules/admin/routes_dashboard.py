"""Dashboard indicators for the panel start screen."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import Numeric, func, select, type_coerce

from sensoria.modules.catalog.models import ProductBook
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.orders.models import Order, StockFulfillmentConflict
from sensoria.modules.vouchers.models import Voucher, VoucherExtensionRequest

from .common import SessionDependency, Staff

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])
WARSAW = ZoneInfo("Europe/Warsaw")


async def _paid(session: SessionDependency, since: datetime) -> tuple[int, int]:
    count, total = (
        await session.execute(
            select(
                func.count(),
                # SUM(bigint) is NUMERIC; coerce so the Money decorator is not applied.
                type_coerce(func.coalesce(func.sum(Order.amount_due_grosz), 0), Numeric),
            ).where(Order.status == "paid", Order.created_at >= since)
        )
    ).one()
    return int(count), int(total)


@router.get("")
async def dashboard(session: SessionDependency, _admin: Staff) -> dict[str, Any]:
    now = datetime.now(UTC)
    local_midnight = datetime.combine(now.astimezone(WARSAW).date(), time.min, tzinfo=WARSAW)
    today = local_midnight.astimezone(UTC)
    week = today - timedelta(days=6)
    month = today - timedelta(days=29)
    paid_today, revenue_today = await _paid(session, today)
    paid_week, revenue_week = await _paid(session, week)
    paid_month, revenue_month = await _paid(session, month)
    awaiting_shipment = int(
        await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.status == "paid",
                Order.fulfillment_status == "awaiting_fulfillment",
                Order.shipping_data["method"].astext.is_not(None),
            )
        )
        or 0
    )
    pending_payment = int(
        await session.scalar(
            select(func.count()).select_from(Order).where(Order.status == "pending_payment")
        )
        or 0
    )
    active_vouchers = int(
        await session.scalar(
            select(func.count())
            .select_from(Voucher)
            .where(Voucher.status == "active", Voucher.valid_until > now)
        )
        or 0
    )
    expiring = int(
        await session.scalar(
            select(func.count())
            .select_from(Voucher)
            .where(
                Voucher.status == "active",
                Voucher.valid_until > now,
                Voucher.valid_until <= now + timedelta(days=30),
            )
        )
        or 0
    )
    pending_requests = int(
        await session.scalar(
            select(func.count())
            .select_from(VoucherExtensionRequest)
            .where(VoucherExtensionRequest.status == "pending")
        )
        or 0
    )
    low_stock = int(
        await session.scalar(
            select(func.count())
            .select_from(ProductBook)
            .where(ProductBook.stock_quantity <= ProductBook.low_stock_threshold)
        )
        or 0
    )
    conflicts = int(
        await session.scalar(
            select(func.count())
            .select_from(StockFulfillmentConflict)
            .where(StockFulfillmentConflict.status == "open")
        )
        or 0
    )
    failed_mails = int(
        await session.scalar(
            select(func.count()).select_from(MailOutbox).where(MailOutbox.status == "failed")
        )
        or 0
    )
    return {
        "generated_at": now.isoformat(),
        "sales": {
            "today": {"orders": paid_today, "revenue_grosz": revenue_today},
            "last_7_days": {"orders": paid_week, "revenue_grosz": revenue_week},
            "last_30_days": {"orders": paid_month, "revenue_grosz": revenue_month},
        },
        "attention": {
            "orders_awaiting_shipment": awaiting_shipment,
            "orders_pending_payment": pending_payment,
            "voucher_extension_requests": pending_requests,
            "low_stock_books": low_stock,
            "stock_conflicts": conflicts,
            "failed_mails": failed_mails,
        },
        "vouchers": {"active": active_vouchers, "expiring_in_30_days": expiring},
    }
