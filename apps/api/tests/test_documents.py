"""Numbered receipts/invoices: gapless numbers, snapshots, deferral without seller config."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.documents.pdf import format_grosz
from sensoria.modules.documents.service import SELLER_SETTING_KEY
from sensoria.shared.app_settings import AppSetting

from . import test_cart
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]

SELLER = {
    "name": "Testowa Firma Sp. z o.o.",
    "street": "Przykładowa 1",
    "postal_code": "10-001",
    "city": "Olsztyn",
    "nip": "5260250995",
}


def test_money_format_uses_integers_only() -> None:
    assert format_grosz(7900) == "79,00 zł"
    assert format_grosz(5) == "0,05 zł"
    assert format_grosz(123456789) == "1 234 567,89 zł"


@pytest.mark.asyncio
async def test_receipt_is_deferred_until_seller_configured_then_issued_once(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    await _pay(client, checkout, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]

    deferred = await client.get(f"/documents/orders/{order_id}?order_token={token}")
    assert deferred.status_code == 200 and deferred.json()["items"] == []

    async with factory() as session:
        session.add(AppSetting(key=SELLER_SETTING_KEY, value=SELLER, description="Test"))
        await session.commit()
    issued = await client.get(f"/documents/orders/{order_id}?order_token={token}")
    items = issued.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "receipt"
    assert items[0]["number"].startswith("PAR/") and items[0]["number"].endswith("/00001")
    again = await client.get(f"/documents/orders/{order_id}?order_token={token}")
    assert again.json()["items"][0]["number"] == items[0]["number"]

    pdf = await client.get(f"/documents/{items[0]['id']}/pdf?order_token={token}")
    assert pdf.status_code == 200
    text = "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Testowa Firma" in text and "79,00 zł" in text and "buyer@example.com" in text
    assert (await client.get(f"/documents/{items[0]['id']}/pdf")).status_code == 401
    assert (
        await client.get(f"/documents/{items[0]['id']}/pdf?order_token={'z' * 20}")
    ).status_code == 404
