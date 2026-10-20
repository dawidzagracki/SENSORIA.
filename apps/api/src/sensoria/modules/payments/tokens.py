"""Stateless capability token that lets the buyer of a guest order read its payment state."""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

from sensoria.config import get_settings


def order_access_token(order_id: UUID) -> str:
    """Derive a per-order token from the server secret; it is never stored."""
    key = get_settings().SECRET_KEY.get_secret_value().encode()
    return hmac.new(key, f"order-access:v1:{order_id}".encode(), hashlib.sha256).hexdigest()


def verify_order_access_token(order_id: UUID, token: str) -> bool:
    return hmac.compare_digest(order_access_token(order_id), token)
