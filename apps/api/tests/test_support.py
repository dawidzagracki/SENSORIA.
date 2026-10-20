"""Withdrawal/return/complaint rules, owner alerts and the staff queue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.ops.alerts import ALERTS_KEY
from sensoria.modules.orders.models import Order
from sensoria.modules.support import service
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError
from sqlalchemy import select

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


@pytest.mark.asyncio
async def test_digital_waiver_blocks_withdrawal_but_complaint_is_allowed(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, checkout, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    base = f"?order_token={token}"
    blocked = await client.post(
        f"/support/cases{base}",
        json={"order_id": order_id, "kind": "withdrawal", "message": "Chcę odstąpić od umowy"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "WITHDRAWAL_DIGITAL_WAIVED"
    assert (
        await client.post(
            "/support/cases",
            json={"order_id": order_id, "kind": "complaint", "message": "Plik nie działa"},
        )
    ).status_code == 401
    complaint = await client.post(
        f"/support/cases{base}",
        json={"order_id": order_id, "kind": "complaint", "message": "Plik PDF nie otwiera się"},
    )
    assert complaint.status_code == 201 and complaint.json()["number"].startswith("ZG-")
    short = await client.post(
        f"/support/cases{base}", json={"order_id": order_id, "kind": "complaint", "message": "x"}
    )
    assert short.status_code == 422
    overview = (await client.get(f"/support/orders/{order_id}{base}")).json()
    assert len(overview["cases"]) == 1 and overview["cases"][0]["status"] == "new"
    async with factory() as session:
        confirmation = await session.scalar(
            select(MailOutbox).where(MailOutbox.template_key == "support_confirmation")
        )
        assert confirmation is not None and confirmation.recipient == "buyer@example.com"


@pytest.mark.asyncio
async def test_voucher_withdrawal_window_alerts_and_staff_queue(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    async with factory() as session:
        session.add(
            AppSetting(key=ALERTS_KEY, value={"email": "wlascicielka@example.com"}, description="t")
        )
        await session.commit()
    checkout = await _checkout(client, ProductKind.VOUCHER, factory)
    await _pay(client, checkout, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    created = await client.post(
        f"/support/cases?order_token={token}",
        json={"order_id": order_id, "kind": "withdrawal", "message": "Rezygnuję z vouchera"},
    )
    assert created.status_code == 201, created.text

    async with factory() as session:
        alert = await session.scalar(
            select(MailOutbox).where(MailOutbox.template_key == "ops_alert")
        )
        assert alert is not None and alert.recipient == "wlascicielka@example.com"
        order = await session.scalar(select(Order))
        assert order is not None
        with pytest.raises(DomainError) as closed:
            await service.create_case(
                session,
                order=order,
                kind="withdrawal",
                order_item_id=None,
                message="Spóźnione odstąpienie",
                now=datetime.now(UTC) + timedelta(days=60),
            )
        assert closed.value.code == "WITHDRAWAL_WINDOW_CLOSED"
        with pytest.raises(DomainError) as not_physical:
            await service.create_case(
                session, order=order, kind="return", order_item_id=None, message="Zwrot paczki"
            )
        assert not_physical.value.code == "RETURN_NOT_PHYSICAL"
        with pytest.raises(DomainError) as old:
            await service.create_case(
                session,
                order=order,
                kind="complaint",
                order_item_id=None,
                message="Reklamacja po latach",
                now=datetime.now(UTC) + timedelta(days=800),
            )
        assert old.value.code == "COMPLAINT_WINDOW_CLOSED"

    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")
    queue = (await client.get("/admin/support-cases?status=new", headers=staff)).json()
    assert queue["total"] == 1
    case_id = queue["items"][0]["id"]
    no_note = await client.patch(
        f"/admin/support-cases/{case_id}", json={"status": "resolved"}, headers=staff
    )
    assert no_note.status_code == 422
    done = await client.patch(
        f"/admin/support-cases/{case_id}",
        json={"status": "resolved", "resolution_note": "Zwrot środków wykonany"},
        headers=staff,
    )
    assert done.json()["status"] == "resolved" and done.json()["resolved_at"]
    overview = (await client.get(f"/support/orders/{order_id}?order_token={token}")).json()
    assert overview["cases"][0]["resolution_note"] == "Zwrot środków wykonany"
