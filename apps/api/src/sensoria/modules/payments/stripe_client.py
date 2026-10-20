"""Minimal Stripe REST adapter: hosted Checkout Session creation and webhook verification."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sensoria.config import Settings
from sensoria.shared.errors import DomainError


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    session_id: str
    url: str
    expires_at: int
    payment_intent_id: str | None


def stripe_configured(settings: Settings) -> bool:
    return settings.STRIPE_SECRET_KEY is not None and settings.STRIPE_WEBHOOK_SECRET is not None


def _post(settings: Settings, path: str, form: list[tuple[str, str]], idem: str) -> dict[str, Any]:
    assert settings.STRIPE_SECRET_KEY is not None
    request = Request(  # noqa: S310 - base URL is operator configuration
        f"{settings.STRIPE_API_BASE.rstrip('/')}{path}",
        data=urlencode(form).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY.get_secret_value()}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Idempotency-Key": idem,
        },
    )
    try:
        with urlopen(request, timeout=settings.STRIPE_TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, ValueError):
        raise DomainError(
            "PAYMENT_PROVIDER_UNAVAILABLE",
            "Operator płatności jest chwilowo niedostępny. Spróbuj ponownie za chwilę.",
            502,
        ) from None
    if not isinstance(payload, dict):
        raise DomainError("PAYMENT_PROVIDER_UNAVAILABLE", "Nieprawidłowa odpowiedź operatora.", 502)
    return payload


async def create_checkout_session(
    settings: Settings,
    *,
    order_id: str,
    order_number: str,
    email: str,
    amount_grosz: int,
    methods: list[str],
    success_url: str,
    cancel_url: str,
    attempt: int,
) -> CheckoutSession:
    """Create a hosted session; amount and currency come only from the stored order."""
    expires = int(time.time()) + 31 * 60
    form: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("client_reference_id", order_id),
        ("customer_email", email),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("expires_at", str(expires)),
        ("line_items[0][quantity]", "1"),
        ("line_items[0][price_data][currency]", "pln"),
        ("line_items[0][price_data][unit_amount]", str(amount_grosz)),
        ("line_items[0][price_data][product_data][name]", f"Zamówienie {order_number}"),
        ("metadata[order_id]", order_id),
        ("payment_intent_data[metadata][order_id]", order_id),
    ]
    form.extend((f"payment_method_types[{i}]", m) for i, m in enumerate(methods))
    data = await asyncio.to_thread(
        _post, settings, "/v1/checkout/sessions", form, f"sensoria-order-{order_id}-{attempt}"
    )
    session_id, url = data.get("id"), data.get("url")
    if not isinstance(session_id, str) or not isinstance(url, str):
        raise DomainError("PAYMENT_PROVIDER_UNAVAILABLE", "Nieprawidłowa odpowiedź operatora.", 502)
    intent = data.get("payment_intent")
    return CheckoutSession(
        session_id=session_id,
        url=url,
        expires_at=int(data.get("expires_at") or expires),
        payment_intent_id=intent if isinstance(intent, str) else None,
    )


def sign_payload(secret: str, payload: bytes, timestamp: int) -> str:
    """Compute the Stripe v1 signature (also used by tests to simulate the provider)."""
    signed = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def verify_webhook(
    settings: Settings, payload: bytes, header: str | None, *, now: float | None = None
) -> dict[str, Any]:
    """Verify signature and timestamp tolerance, then return the decoded event."""
    invalid = DomainError("PAYMENT_WEBHOOK_INVALID", "Nieprawidłowy podpis webhooka.", 400)
    if settings.STRIPE_WEBHOOK_SECRET is None or not header:
        raise invalid
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise invalid
    if abs((now if now is not None else time.time()) - timestamp) > (
        settings.PAYMENT_WEBHOOK_TOLERANCE_SECONDS
    ):
        raise invalid
    expected = sign_payload(settings.STRIPE_WEBHOOK_SECRET.get_secret_value(), payload, timestamp)
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise invalid
    try:
        event = json.loads(payload)
    except ValueError:
        raise invalid from None
    if not isinstance(event, dict) or not isinstance(event.get("id"), str):
        raise invalid
    return event
