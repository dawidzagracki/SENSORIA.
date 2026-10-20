"""Discount codes, information pages and sales reports with CSV safety."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sensoria.config import Settings
from sensoria.modules.admin.common import csv_cell
from sensoria.modules.catalog.types import ProductKind

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


def test_csv_cell_neutralizes_formulas() -> None:
    for danger in ("=1+1", "+cmd", "-2", "@SUM(A1)", "\tx", "\rx"):
        assert csv_cell(danger).startswith("'")
    assert csv_cell("zwykły") == "zwykły" and csv_cell(None) == ""


@pytest.mark.asyncio
async def test_discount_codes_owner_only_and_validated(cart_environment: CartEnvironment) -> None:
    client, factory = cart_environment
    await create_admin(factory, "owner@example.com", "owner")
    await create_admin(factory, "staff@example.com", "staff")
    owner = await admin_headers(client, "owner@example.com")
    staff = await admin_headers(client, "staff@example.com")
    body = {"code": "LATO10", "type": "percentage", "value": 10, "max_uses": 5}
    assert (await client.post("/admin/discount-codes", json=body, headers=staff)).status_code == 403
    created = await client.post("/admin/discount-codes", json=body, headers=owner)
    assert created.status_code == 201 and created.json()["used_count"] == 0
    assert (
        await client.post("/admin/discount-codes", json={**body, "code": "lato10"}, headers=owner)
    ).status_code == 409
    bad = await client.post(
        "/admin/discount-codes", json={**body, "code": "BAD", "value": 150}, headers=owner
    )
    assert bad.status_code == 422
    cid = created.json()["id"]
    off = await client.patch(
        f"/admin/discount-codes/{cid}", json={"is_active": False}, headers=owner
    )
    assert off.json()["is_active"] is False
    listing = (await client.get("/admin/discount-codes", headers=staff)).json()
    assert listing["total"] == 1 and listing["items"][0]["code"] == "LATO10"


@pytest.mark.asyncio
async def test_pages_publish_flow_and_public_read(cart_environment: CartEnvironment) -> None:
    client, factory = cart_environment
    await create_admin(factory, "owner@example.com", "owner")
    owner = await admin_headers(client, "owner@example.com")
    page = {
        "slug": "regulamin",
        "title": "Regulamin",
        "blocks": [{"type": "h2", "text": "§1"}, {"type": "p", "text": "<script>x</script>"}],
    }
    saved = await client.put("/admin/pages/regulamin", json=page, headers=owner)
    assert saved.status_code == 200 and saved.json()["status"] == "draft"
    assert (await client.get("/pages/regulamin")).status_code == 404  # drafts are private
    mismatch = await client.put("/admin/pages/inna", json=page, headers=owner)
    assert mismatch.status_code == 422
    assert (await client.post("/admin/pages/regulamin/publish", headers=owner)).status_code == 200
    public = (await client.get("/pages/regulamin")).json()
    assert public["blocks"][1]["text"] == "<script>x</script>"  # data only; UI renders as text
    assert [p["slug"] for p in (await client.get("/pages")).json()["items"]] == ["regulamin"]
    await client.post("/admin/pages/regulamin/unpublish", headers=owner)
    assert (await client.get("/pages/regulamin")).status_code == 404


@pytest.mark.asyncio
async def test_sales_report_and_csv(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, checkout, factory)
    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")
    today = date.today()
    params = f"date_from={today - timedelta(days=1)}&date_to={today + timedelta(days=1)}"
    report = (await client.get(f"/admin/reports/sales?{params}", headers=staff)).json()
    assert report["totals"]["orders"] == 1 and report["totals"]["gross_grosz"] == 7900
    assert report["totals"]["net_grosz"] + report["totals"]["tax_grosz"] == 7900
    assert report["vat"][0]["vat_label"] == "5%"
    monthly = (await client.get(f"/admin/reports/sales?{params}&group=month", headers=staff)).json()
    assert len(monthly["periods"]) == 1 and len(monthly["periods"][0]["period"]) == 7
    csv_response = await client.get(f"/admin/reports/sales.csv?{params}", headers=staff)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    lines = csv_response.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Okres;Zamówienia") and lines[-1].startswith("RAZEM;1;79.00")
    assert (
        await client.get(
            "/admin/reports/sales?date_from=2026-01-01&date_to=2025-01-01", headers=staff
        )
    ).status_code == 422
    assert (
        await client.get(
            "/admin/reports/sales?date_from=2020-01-01&date_to=2026-01-01", headers=staff
        )
    ).status_code == 422
    products = (await client.get(f"/admin/reports/products?{params}", headers=staff)).json()
    assert products["items"][0]["quantity"] == 1
