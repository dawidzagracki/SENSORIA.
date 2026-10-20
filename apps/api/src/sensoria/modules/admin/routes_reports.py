"""Sales reports built from frozen order snapshots, with formula-safe CSV export."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from sensoria.modules.orders.models import Order, OrderItem
from sensoria.shared.errors import DomainError

from .common import SessionDependency, Staff, csv_cell

router = APIRouter(prefix="/reports", tags=["admin-reports"])
WARSAW = ZoneInfo("Europe/Warsaw")
MAX_RANGE_DAYS = 366
MAX_ORDERS = 50_000


def _bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    if date_to < date_from:
        raise DomainError("REPORT_RANGE_INVALID", "Data końcowa jest przed początkową.", 422)
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise DomainError("REPORT_RANGE_TOO_LARGE", "Zakres nie może przekraczać 366 dni.", 422)
    start = datetime.combine(date_from, time.min, tzinfo=WARSAW).astimezone(UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=WARSAW).astimezone(UTC)
    return start, end


def _period(moment: datetime, group: str) -> str:
    local = moment.astimezone(WARSAW)
    return local.strftime("%Y-%m") if group == "month" else local.strftime("%Y-%m-%d")


async def build_sales(
    session: SessionDependency, date_from: date, date_to: date, group: str
) -> dict[str, Any]:
    start, end = _bounds(date_from, date_to)
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.status == "paid", Order.created_at >= start, Order.created_at < end)
                .order_by(Order.created_at)
                .limit(MAX_ORDERS + 1)
            )
        ).all()
    )
    if len(orders) > MAX_ORDERS:
        raise DomainError("REPORT_TOO_LARGE", "Zawęż zakres dat raportu.", 422)
    periods: dict[str, dict[str, int]] = defaultdict(
        lambda: {"orders": 0, "gross_grosz": 0, "net_grosz": 0, "tax_grosz": 0, "discount_grosz": 0}
    )
    vat: dict[str, dict[str, int]] = defaultdict(
        lambda: {"gross_grosz": 0, "net_grosz": 0, "tax_grosz": 0}
    )
    for order in orders:
        calc = order.calculation_snapshot
        groups = list(calc.get("vat_groups", []))
        if calc.get("exempt", {}).get("gross_grosz"):
            groups.append(calc["exempt"])
        delivery = calc.get("delivery") or {}
        if delivery.get("resolved") and delivery.get("gross_grosz", 0) > 0:
            groups.append(delivery)
        row = periods[_period(order.created_at, group)]
        row["orders"] += 1
        row["gross_grosz"] += order.amount_due_grosz
        row["discount_grosz"] += int(calc.get("discount_grosz", 0))
        for g in groups:
            if not int(g.get("gross_grosz", 0)):
                continue
            net, tax, gross = int(g["net_grosz"]), int(g["tax_grosz"]), int(g["gross_grosz"])
            label = str(g.get("vat_label") or "—")
            row["net_grosz"] += net
            row["tax_grosz"] += tax
            vat[label]["net_grosz"] += net
            vat[label]["tax_grosz"] += tax
            vat[label]["gross_grosz"] += gross
    totals = {
        key: sum(p[key] for p in periods.values())
        for key in ("orders", "gross_grosz", "net_grosz", "tax_grosz", "discount_grosz")
    }
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "group": group,
        "totals": totals,
        "periods": [{"period": k, **v} for k, v in sorted(periods.items())],
        "vat": [{"vat_label": k, **v} for k, v in sorted(vat.items())],
    }


@router.get("/sales")
async def sales_report(
    session: SessionDependency,
    _admin: Staff,
    date_from: date,
    date_to: date,
    group: Annotated[str, Query(pattern="^(day|month)$")] = "day",
) -> dict[str, Any]:
    return await build_sales(session, date_from, date_to, group)


@router.get("/sales.csv")
async def sales_csv(
    session: SessionDependency,
    _admin: Staff,
    date_from: date,
    date_to: date,
    group: Annotated[str, Query(pattern="^(day|month)$")] = "day",
) -> Response:
    report = await build_sales(session, date_from, date_to, group)
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Okres", "Zamówienia", "Brutto", "Netto", "Podatek", "Rabaty"])

    def money(value: int) -> str:
        return f"{value // 100}.{value % 100:02d}"

    for p in report["periods"]:
        writer.writerow(
            [
                csv_cell(p["period"]),
                p["orders"],
                money(p["gross_grosz"]),
                money(p["net_grosz"]),
                money(p["tax_grosz"]),
                money(p["discount_grosz"]),
            ]
        )
    t = report["totals"]
    writer.writerow(
        [
            "RAZEM",
            t["orders"],
            money(t["gross_grosz"]),
            money(t["net_grosz"]),
            money(t["tax_grosz"]),
            money(t["discount_grosz"]),
        ]
    )
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="sprzedaz-{date_from}-{date_to}.csv"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/products")
async def product_report(
    session: SessionDependency, _admin: Staff, date_from: date, date_to: date
) -> dict[str, Any]:
    start, end = _bounds(date_from, date_to)
    rows = (
        await session.execute(
            select(OrderItem.product_name_snapshot, OrderItem.quantity, OrderItem.item_settlement)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status == "paid", Order.created_at >= start, Order.created_at < end)
        )
    ).all()
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"quantity": 0, "gross_grosz": 0})
    for name, quantity, settlement in rows:
        entry = totals[name or "—"]
        entry["quantity"] += int(quantity)
        entry["gross_grosz"] += int(settlement.get("gross_grosz", 0))
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1]["gross_grosz"], kv[0]))
    return {"items": [{"name": n, **v} for n, v in ranked[:100]]}
