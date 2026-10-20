"""Owner settings editor: validation, persistence and effect on documents."""

from __future__ import annotations

import pytest
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


@pytest.mark.asyncio
async def test_settings_are_owner_only_validated_and_used(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    await create_admin(factory, "owner@example.com", "owner")
    await create_admin(factory, "staff@example.com", "staff")
    owner = await admin_headers(client, "owner@example.com")
    staff = await admin_headers(client, "staff@example.com")
    assert (await client.get("/admin/settings", headers=staff)).status_code == 403
    listing = (await client.get("/admin/settings", headers=owner)).json()["items"]
    assert {i["key"] for i in listing} >= {
        "company.seller.v1",
        "orders.delivery.v1",
        "ops.alerts.v1",
    }

    bad = await client.put(
        "/admin/settings/ops.alerts.v1", json={"value": {"email": "nie-email"}}, headers=owner
    )
    assert bad.status_code == 422 and "e-mail" in bad.json()["error"]["message"]
    assert (
        await client.put("/admin/settings/secret.key", json={"value": {}}, headers=owner)
    ).status_code == 404
    extra = await client.put(
        "/admin/settings/ops.alerts.v1", json={"value": {"email": "a@b.pl", "x": 1}}, headers=owner
    )
    assert extra.status_code == 422
    http_url = await client.put(
        "/admin/settings/vouchers.public.v1",
        json={"value": {"booking_url": "http://insecure.example"}},
        headers=owner,
    )
    assert http_url.status_code == 422
    negative = await client.put(
        "/admin/settings/orders.delivery.v1",
        json={
            "value": {
                "parcel_locker_cost_grosz": -1,
                "courier_cost_grosz": 1,
                "free_shipping_threshold_grosz": 1,
                "incentive_threshold_grosz": 1,
                "vat_rate": "RATE_23",
            }
        },
        headers=owner,
    )
    assert negative.status_code == 422

    saved = await client.put(
        "/admin/settings/company.seller.v1",
        json={
            "value": {
                "name": "Sensoria Terapia",
                "street": "Knosały 7B/A",
                "postal_code": "10-015",
                "city": "Olsztyn",
                "nip": "5260250995",
            }
        },
        headers=owner,
    )
    assert saved.status_code == 200
    # Settings take effect immediately: a paid order now gets its document.
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, checkout, factory)
    docs = await client.get(
        f"/documents/orders/{checkout['order_id']}?order_token={checkout['access_token']}"
    )
    assert docs.json()["items"][0]["kind"] == "receipt"
    again = await client.put(
        "/admin/settings/company.seller.v1",
        json={
            "value": {
                "name": "Zmieniona",
                "street": "ul. Nowa 1",
                "postal_code": "10-001",
                "city": "Olsztyn",
            }
        },
        headers=owner,
    )
    assert again.json()["value"]["name"] == "Zmieniona"
