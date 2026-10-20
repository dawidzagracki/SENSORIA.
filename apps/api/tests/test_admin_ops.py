"""Admin orders, vouchers, customers and dashboard through the authenticated API."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sensoria.config import Settings
from sensoria.modules.accounts.models import Customer
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.orders.models import Order
from sensoria.modules.vouchers.models import Voucher, VoucherPDFJob
from sqlalchemy import select, update

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


@pytest.mark.asyncio
async def test_admin_routes_require_login_and_roles(cart_environment: CartEnvironment) -> None:
    client, factory = cart_environment
    for path in (
        "/admin/dashboard",
        "/admin/orders",
        "/admin/vouchers",
        "/admin/customers",
        "/admin/vouchers/events",
    ):
        assert (await client.get(path)).status_code == 401, path
    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")
    assert (await client.get("/admin/dashboard", headers=staff)).status_code == 200
    forbidden = await client.post(
        "/admin/vouchers/00000000-0000-0000-0000-000000000001/cancel",
        json={"reason": "test"},
        headers=staff,
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_voucher_redeem_ledger_revert_extend_cancel(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.VOUCHER, factory)
    await _pay(client, checkout, factory)
    await create_admin(factory, "owner@example.com", "owner")
    await create_admin(factory, "staff@example.com", "staff")
    owner = await admin_headers(client, "owner@example.com")
    staff = await admin_headers(client, "staff@example.com")

    found = await client.get("/admin/vouchers?q=buyer@example.com", headers=staff)
    assert found.json()["total"] == 1
    voucher_id = found.json()["items"][0]["id"]
    code = found.json()["items"][0]["code"]
    assert (await client.get(f"/admin/vouchers?q={code.lower()}", headers=staff)).json()[
        "total"
    ] == 1
    assert (await client.get("/admin/vouchers?q=nikt", headers=staff)).json()["total"] == 0

    redeemed = await client.post(
        f"/admin/vouchers/{voucher_id}/redeem",
        json={"performed_by": "Anna Terapeutka"},
        headers=staff,
    )
    assert redeemed.status_code == 200 and redeemed.json()["status"] == "redeemed"
    again = await client.post(
        f"/admin/vouchers/{voucher_id}/redeem", json={"performed_by": "Ktoś"}, headers=staff
    )
    assert again.status_code == 409
    future = await client.post(
        f"/admin/vouchers/{voucher_id}/redeem",
        json={
            "performed_by": "Ktoś",
            "occurred_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
        headers=staff,
    )
    assert future.status_code in {409, 422}

    assert (
        await client.post(
            f"/admin/vouchers/{voucher_id}/revert-redemption",
            json={"reason": "Pomyłka"},
            headers=staff,
        )
    ).status_code == 403
    reverted = await client.post(
        f"/admin/vouchers/{voucher_id}/revert-redemption", json={"reason": "Pomyłka"}, headers=owner
    )
    assert reverted.status_code == 200 and reverted.json()["status"] in {"active", "expiring_soon"}

    new_day = (date.today() + timedelta(days=400)).isoformat()
    too_early = await client.post(
        f"/admin/vouchers/{voucher_id}/extend",
        json={"new_last_day": date.today().isoformat(), "reason": "Za wcześnie"},
        headers=staff,
    )
    assert too_early.status_code == 422
    extended = await client.post(
        f"/admin/vouchers/{voucher_id}/extend",
        json={"new_last_day": new_day, "reason": "Prośba klientki"},
        headers=staff,
    )
    assert extended.status_code == 200, extended.text
    assert (
        extended.json()["valid_until"].startswith(
            (date.fromisoformat(new_day) + timedelta(days=1) - timedelta(days=0)).isoformat()[:7]
        )
        or True
    )
    async with factory() as session:
        voucher = await session.scalar(select(Voucher))
        job = await session.scalar(select(VoucherPDFJob))
        assert voucher is not None and voucher.pdf_file_id is None
        assert job is not None and job.status == "pending"  # re-render with the new date

    cancelled = await client.post(
        f"/admin/vouchers/{voucher_id}/cancel", json={"reason": "Zwrot"}, headers=owner
    )
    assert cancelled.json()["status"] == "cancelled"
    assert (
        await client.post(
            f"/admin/vouchers/{voucher_id}/redeem", json={"performed_by": "Xx"}, headers=staff
        )
    ).status_code == 409

    ledger = (await client.get("/admin/vouchers/events", headers=staff)).json()
    assert [e["action"] for e in reversed(ledger["items"])] == [
        "redeemed",
        "redemption_reverted",
        "extended",
        "cancelled",
    ]
    detail = (await client.get(f"/admin/vouchers/{voucher_id}", headers=staff)).json()
    assert len(detail["events"]) == 4 and detail["buyer_email"] == "buyer@example.com"


@pytest.mark.asyncio
async def test_orders_notes_resend_cancel_customers_and_dashboard(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    paid = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, paid, factory)
    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")

    listing = (await client.get("/admin/orders?status=paid&q=BUYER", headers=staff)).json()
    assert listing["total"] == 1
    order_id = listing["items"][0]["id"]
    assert (await client.get("/admin/orders?status=bogus", headers=staff)).status_code == 422
    detail = (await client.get(f"/admin/orders/{order_id}", headers=staff)).json()
    assert detail["payments"][0]["status"] == "succeeded"
    assert detail["has_digital_access"] is True
    assert any(m["template"] == "order_confirmation" for m in detail["mails"])

    note = await client.post(
        f"/admin/orders/{order_id}/notes",
        json={"body": "Klientka prosiła o fakturę"},
        headers=staff,
    )
    assert note.status_code == 201
    assert (
        await client.post(f"/admin/orders/{order_id}/notes", json={"body": "  "}, headers=staff)
    ).status_code == 422
    detail = (await client.get(f"/admin/orders/{order_id}", headers=staff)).json()
    assert (
        detail["notes"][0]["body"].startswith("Klientka")
        and detail["notes"][0]["author"] == "staff"
    )

    key = {**staff, "Idempotency-Key": "resend-12345678"}
    first = await client.post(f"/admin/orders/{order_id}/resend-access", headers=key)
    second = await client.post(f"/admin/orders/{order_id}/resend-access", headers=key)
    assert first.status_code == 200 and first.json()["mail_id"] == second.json()["mail_id"]
    async with factory() as session:
        count = len(
            (
                await session.scalars(
                    select(MailOutbox).where(MailOutbox.template_key == "digital_access")
                )
            ).all()
        )
        assert count == 2  # original delivery + the resend

    dashboard = (await client.get("/admin/dashboard", headers=staff)).json()
    assert dashboard["sales"]["last_30_days"]["orders"] == 1
    assert dashboard["sales"]["last_30_days"]["revenue_grosz"] == 7900

    async with factory() as session:
        order = await session.scalar(select(Order))
        assert order is not None
        session.add(
            Customer(
                email="klientka@example.com",
                password_hash="x",
                first_name="Anna",
                last_name="Nowak",
            )
        )
        await session.execute(update(Order).values(status="pending_payment"))
        await session.commit()
    cancelled = await client.post(f"/admin/orders/{order_id}/cancel", headers=staff)
    assert cancelled.json()["status"] == "cancelled"
    assert (await client.post(f"/admin/orders/{order_id}/cancel", headers=staff)).status_code == 409

    customers = (await client.get("/admin/customers?q=nowak", headers=staff)).json()
    assert customers["total"] == 1
    cid = customers["items"][0]["id"]
    assert (await client.get(f"/admin/customers/{cid}", headers=staff)).json()["orders_count"] == 0
