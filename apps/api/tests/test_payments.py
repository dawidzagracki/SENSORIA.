"""Stripe hosted-checkout flow: session start, signed webhooks, idempotency and failures."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio  # noqa: F401
from httpx import AsyncClient
from pydantic import SecretStr
from sensoria.config import Settings, get_settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.orders.models import Order
from sensoria.modules.payments import service as payment_service
from sensoria.modules.payments.models import Payment, PaymentEvent
from sensoria.modules.payments.stripe_client import (
    CheckoutSession,
    sign_payload,
    verify_webhook,
)
from sensoria.modules.vouchers.models import Voucher
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate
from sqlalchemy import select

from . import test_cart
from .test_cart import CartEnvironment, _cookie, _product, _publish

cart_environment = test_cart.cart_environment

WEBHOOK_SECRET = "whsec_test_secret_value"


@pytest.fixture
def stripe_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    base = get_settings()
    configured = base.model_copy(
        update={
            "STRIPE_SECRET_KEY": SecretStr("sk_test_fake"),
            "STRIPE_WEBHOOK_SECRET": SecretStr(WEBHOOK_SECRET),
        }
    )
    for module in (
        "sensoria.modules.payments.router",
        "sensoria.modules.orders.checkout",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: configured)
    created: list[dict[str, Any]] = []

    async def fake_create(settings: Settings, **kwargs: Any) -> CheckoutSession:
        created.append(kwargs)
        number = len(created)
        return CheckoutSession(
            session_id=f"cs_test_{kwargs['order_id'][:8]}_{number}",
            url=f"https://checkout.stripe.test/pay/{number}",
            expires_at=int(time.time()) + 1800,
            payment_intent_id=f"pi_test_{number}",
        )

    monkeypatch.setattr(payment_service, "create_checkout_session", fake_create)
    configured.__dict__["_created"] = created
    yield configured


async def _checkout(
    client: AsyncClient, kind: ProductKind, factory: Any, **extra: Any
) -> dict[str, Any]:
    product = await _publish(
        factory,
        _product(kind, price=7900, vat_rate=VatRate.RATE_5, **extra),
    )
    item: dict[str, Any] = {"product_id": str(product.id), "quantity": 1}
    if kind is ProductKind.VOUCHER:
        assert product.voucher is not None
        item["variant_id"] = str(product.voucher.variants[0].id)
    added = await client.post("/cart/items", json=item)
    assert added.status_code == 200, added.text
    config = (await client.get("/cart/checkout-config")).json()
    payload = {
        "email": "buyer@example.com",
        "invoice_kind": "private",
        "payment_method": "blik",
        "terms_accepted": True,
        "digital_consent": kind is ProductKind.DIGITAL,
        "consent_version": config["consent_version"],
    }
    response = await client.post(
        "/cart/checkout",
        json=payload,
        headers={"Idempotency-Key": "pay-key", "Cookie": f"cart_token={_cookie(added)}"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _event(event_type: str, session_id: str, **obj: Any) -> bytes:
    return json.dumps(
        {
            "id": f"evt_{event_type}_{session_id}_{obj.get('n', 0)}",
            "type": event_type,
            "data": {"object": {"id": session_id, **{k: v for k, v in obj.items() if k != "n"}}},
        }
    ).encode()


async def _post_event(client: AsyncClient, body: bytes, *, secret: str = WEBHOOK_SECRET) -> Any:
    ts = int(time.time())
    header = f"t={ts},v1={sign_payload(secret, body, ts)}"
    return await client.post(
        "/payments/webhooks/stripe", content=body, headers={"Stripe-Signature": header}
    )


def test_signature_verification_rejects_tampering_and_stale_timestamp(
    stripe_settings: Settings,
) -> None:
    body = b'{"id":"evt_1","type":"x"}'
    ts = int(time.time())
    good = f"t={ts},v1={sign_payload(WEBHOOK_SECRET, body, ts)}"
    assert verify_webhook(stripe_settings, body, good)["id"] == "evt_1"
    with pytest.raises(DomainError):
        verify_webhook(stripe_settings, body + b" ", good)
    with pytest.raises(DomainError):
        verify_webhook(stripe_settings, body, None)
    stale = ts - 10_000
    with pytest.raises(DomainError):
        verify_webhook(
            stripe_settings, body, f"t={stale},v1={sign_payload(WEBHOOK_SECRET, body, stale)}"
        )


@pytest.mark.asyncio
async def test_unsigned_webhook_is_rejected(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, _ = cart_environment
    response = await client.post("/payments/webhooks/stripe", content=b"{}")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_payment_flow_marks_order_paid_once_and_issues_voucher(
    cart_environment: CartEnvironment, stripe_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.VOUCHER, factory)
    assert checkout["payment_integration"] == "stripe"
    order_id, token = checkout["order_id"], checkout["access_token"]

    bad = await client.post(f"/payments/orders/{order_id}/session?token={'x' * 20}")
    assert bad.status_code == 404
    started = await client.post(f"/payments/orders/{order_id}/session?token={token}")
    assert started.status_code == 200, started.text
    again = await client.post(f"/payments/orders/{order_id}/session?token={token}")
    assert again.json()["payment_id"] == started.json()["payment_id"]
    assert len(stripe_settings.__dict__["_created"]) == 1
    assert stripe_settings.__dict__["_created"][0]["amount_grosz"] == 9500

    async with factory() as session:
        payment = await session.scalar(select(Payment))
        assert payment is not None
        session_id = payment.provider_session_id

    wrong_amount = await _post_event(
        client,
        _event(
            "checkout.session.completed",
            session_id,
            payment_status="paid",
            amount_total=1,
            currency="pln",
            n=1,
        ),
    )
    assert wrong_amount.json()["outcome"] == "amount_mismatch"
    async with factory() as session:
        order = await session.get(Order, UUID(order_id))
        assert order is not None and order.status == "pending_payment"

    # Mismatch closed the pending attempt; the buyer can start a new one.
    restarted = await client.post(f"/payments/orders/{order_id}/session?token={token}")
    assert restarted.status_code == 200
    assert restarted.json()["attempt"] == 2
    async with factory() as session:
        second = await session.scalar(select(Payment).where(Payment.attempt == 2))
        assert second is not None
        session_id = second.provider_session_id

    body = _event(
        "checkout.session.completed",
        session_id,
        payment_status="paid",
        amount_total=9500,
        currency="pln",
    )
    first = await _post_event(client, body)
    replay = await _post_event(client, body)
    assert first.json()["outcome"] == "paid"
    assert replay.json()["outcome"] == "duplicate"
    async with factory() as session:
        order = await session.get(Order, UUID(order_id))
        assert order is not None and order.status == "paid"
        vouchers = list((await session.scalars(select(Voucher))).all())
        assert len(vouchers) == 1
        events = list((await session.scalars(select(PaymentEvent))).all())
        assert {e.outcome for e in events} >= {"paid", "amount_mismatch"}

    status = await client.get(f"/payments/orders/{order_id}?token={token}")
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "paid" and data["payment_status"] == "succeeded"
    assert data["email_masked"] == "b***@example.com"
    assert data["can_retry_payment"] is False
    paid_again = await client.post(f"/payments/orders/{order_id}/session?token={token}")
    assert paid_again.status_code == 409


@pytest.mark.asyncio
async def test_async_failure_keeps_order_payable_and_allows_retry(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    await client.post(f"/payments/orders/{order_id}/session?token={token}")
    async with factory() as session:
        sid = (await session.scalar(select(Payment.provider_session_id))) or ""
    failed = await _post_event(
        client, _event("checkout.session.async_payment_failed", sid, payment_status="unpaid")
    )
    assert failed.json()["outcome"] == "failed"
    status = (await client.get(f"/payments/orders/{order_id}?token={token}")).json()
    assert status["status"] == "pending_payment"
    assert status["payment_status"] == "failed"
    assert status["can_retry_payment"] is True
    retry = await client.post(f"/payments/orders/{order_id}/session?token={token}")
    assert retry.status_code == 200 and retry.json()["attempt"] == 2


@pytest.mark.asyncio
async def test_session_requires_configured_provider(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    assert checkout["payment_integration"] == "not_configured"
    response = await client.post(
        f"/payments/orders/{checkout['order_id']}/session?token={checkout['access_token']}"
    )
    assert response.status_code == 503
