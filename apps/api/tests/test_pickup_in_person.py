"""Studio pickup: free, no address, ready-for-pickup mail and pickup confirmation."""

from __future__ import annotations

import pytest
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.bridge import dispatch_legacy_jobs
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.orders.models import Order
from sqlalchemy import select

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment, _cookie, _product, _publish
from .test_library import _pay, uploads
from .test_payments import stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


@pytest.mark.asyncio
async def test_book_collected_in_studio_flow(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=5900, stock=3))
    added = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    cookie = {"Cookie": f"cart_token={_cookie(added)}"}
    chosen = await client.patch(
        "/cart/delivery", json={"method": "pickup_in_person"}, headers=cookie
    )
    assert chosen.status_code == 200, chosen.text
    body = chosen.json()
    quotes = {q["method"]: q["gross_grosz"] for q in body["delivery"]["available_quotes"]}
    assert quotes["pickup_in_person"] == 0 and quotes["courier"] > 0
    assert body["calculation"]["amount_due_grosz"] == 5900  # nothing added for delivery

    config = (await client.get("/cart/checkout-config")).json()
    checkout = await client.post(
        "/cart/checkout",
        json={
            "email": "buyer@example.com",
            "first_name": "Anna",
            "last_name": "Nowak",
            "phone": "600100200",
            "delivery_method": "pickup_in_person",
            "invoice_kind": "private",
            "payment_method": "blik",
            "terms_accepted": True,
            "consent_version": config["consent_version"],
        },
        headers={"Idempotency-Key": "pickup-key", **cookie},
    )
    assert checkout.status_code == 201, checkout.text
    data = checkout.json()
    assert data["amount_due_grosz"] == 5900
    await _pay(client, data, factory)

    async with factory() as session:
        order = await session.scalar(select(Order))
        assert order is not None and (order.shipping_data or {})["method"] == "pickup_in_person"
        assert order.delivery_point_snapshot is None

    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")
    ready = await client.post(f"/admin/orders/{data['order_id']}/pickup-ready", headers=staff)
    assert ready.status_code == 200 and ready.json()["fulfillment_status"] == "ready_for_pickup"
    await dispatch_legacy_jobs(factory)
    async with factory() as session:
        mail = await session.scalar(
            select(MailOutbox).where(MailOutbox.template_key == "pickup_ready")
        )
        assert mail is not None and mail.recipient == "buyer@example.com"
    done = await client.post(f"/admin/orders/{data['order_id']}/picked-up", headers=staff)
    assert done.json()["fulfillment_status"] == "picked_up"
