"""Verified-purchase reviews, moderation and consent-based review requests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.mail.models import MailOutbox
from sensoria.modules.reviews.service import clean_text, queue_review_requests
from sqlalchemy import select

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


def test_clean_text_strips_controls_and_normalizes() -> None:
    assert clean_text("A\x00B\x07 \t C", multiline=False) == "AB C"
    assert clean_text("a\n\n\n\nb  c", multiline=True) == "a\n\nb c"


async def _item_id(client: AsyncClient, order_id: str, token: str) -> str:
    eligible = await client.get(f"/reviews/eligible?order_id={order_id}&order_token={token}")
    assert eligible.status_code == 200, eligible.text
    return str(eligible.json()["items"][0]["order_item_id"])


@pytest.mark.asyncio
async def test_review_lifecycle_with_moderation(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    slug = None
    async with factory() as session:
        from sensoria.modules.catalog.models import Product
        from sensoria.modules.orders.models import OrderItem

        slug = await session.scalar(
            select(Product.slug).join(OrderItem, OrderItem.product_id == Product.id)
        )
    assert slug

    assert (await client.get(f"/reviews/eligible?order_id={order_id}&order_token={token}")).json()[
        "items"
    ] == []
    await _pay(client, checkout, factory)
    item = await _item_id(client, order_id, token)

    body = {
        "order_id": order_id,
        "order_item_id": item,
        "rating": 5,
        "body": "Świetna książka <b>polecam</b>!",
    }
    unauth = await client.post("/reviews", json=body)
    assert unauth.status_code == 401
    wrong = await client.post(f"/reviews?order_token={'x' * 20}", json=body)
    assert wrong.status_code == 404
    short = await client.post(f"/reviews?order_token={token}", json={**body, "body": "ok"})
    assert short.status_code == 422
    bad_rating = await client.post(f"/reviews?order_token={token}", json={**body, "rating": 6})
    assert bad_rating.status_code == 422
    created = await client.post(f"/reviews?order_token={token}", json=body)
    assert created.status_code == 201 and created.json()["status"] == "pending"
    dup = await client.post(f"/reviews?order_token={token}", json=body)
    assert dup.status_code == 409

    public = (await client.get(f"/reviews/products/{slug}")).json()
    assert public["total"] == 0 and public["summary"]["count"] == 0

    await create_admin(factory, "staff@example.com", "staff")
    staff = await admin_headers(client, "staff@example.com")
    queue = (await client.get("/admin/reviews", headers=staff)).json()
    assert queue["total"] == 1 and queue["items"][0]["author"] == "Klientka"
    review_id = queue["items"][0]["id"]
    approved = await client.post(
        f"/admin/reviews/{review_id}/decision", json={"approve": True}, headers=staff
    )
    assert approved.json()["status"] == "approved"

    public = (await client.get(f"/reviews/products/{slug}")).json()
    assert public["total"] == 1 and public["summary"]["average"] == 5.0
    assert public["items"][0]["body"] == "Świetna książka <b>polecam</b>!"  # data, not markup
    assert "buyer@example.com" not in str(public)
    rejected = await client.post(
        f"/admin/reviews/{review_id}/decision",
        json={"approve": False, "note": "Spam"},
        headers=staff,
    )
    assert rejected.json()["status"] == "rejected"
    assert (await client.get(f"/reviews/products/{slug}")).json()["total"] == 0


@pytest.mark.asyncio
async def test_review_request_requires_consent_and_is_sent_once(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    no_consent = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, no_consent, factory)
    later = datetime.now(UTC) + timedelta(days=8)
    assert await queue_review_requests(factory, now=later) == 0
    assert await queue_review_requests(factory, now=datetime.now(UTC)) == 0  # too early anyway


@pytest.mark.asyncio
async def test_review_request_with_checkout_consent(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(
        client, ProductKind.DIGITAL, factory, payload_extra={"review_requests_consent": True}
    )
    await _pay(client, checkout, factory)
    too_early = await queue_review_requests(factory, now=datetime.now(UTC) + timedelta(days=2))
    assert too_early == 0
    later = datetime.now(UTC) + timedelta(days=8)
    assert await queue_review_requests(factory, now=later) == 1
    assert await queue_review_requests(factory, now=later) == 0  # exactly once
    async with factory() as session:
        mail = await session.scalar(
            select(MailOutbox).where(MailOutbox.template_key == "review_request")
        )
        assert mail is not None and mail.recipient == "buyer@example.com"
        assert "/opinie/nowa?order=" in mail.text_body and "token=" in mail.text_body
        assert "zgodę" in mail.html_body or "zgod" in mail.html_body
