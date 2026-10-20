"""Voucher PDF worker, guest voucher access and anonymous verification throttling."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader
from sensoria.config import Settings
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.vouchers import router as voucher_router
from sensoria.modules.vouchers.models import Voucher, VoucherPDFJob
from sensoria.modules.vouchers.pdf_worker import process_voucher_pdf_jobs
from sqlalchemy import select

from . import test_cart
from .test_cart import CartEnvironment
from .test_library import _pay, uploads
from .test_payments import _checkout, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "stripe_settings", "uploads"]


@pytest.mark.asyncio
async def test_paid_voucher_gets_pdf_via_worker_and_public_verification(
    cart_environment: CartEnvironment, stripe_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.VOUCHER, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    await _pay(client, checkout, factory)

    listed = (await client.get(f"/vouchers/orders/{order_id}?order_token={token}")).json()["items"]
    assert len(listed) == 1 and listed[0]["pdf_ready"] is False
    preparing = await client.get(f"/vouchers/{listed[0]['id']}/pdf?order_token={token}")
    assert preparing.status_code == 409

    done = await process_voucher_pdf_jobs(factory)
    assert done == 1
    async with factory() as session:
        job = await session.scalar(select(VoucherPDFJob))
        assert job is not None and job.status == "complete"
        voucher = await session.scalar(select(Voucher))
        assert voucher is not None and voucher.pdf_file_id is not None
        code = voucher.code
    assert await process_voucher_pdf_jobs(factory) == 0

    pdf = await client.get(f"/vouchers/{listed[0]['id']}/pdf?order_token={token}")
    assert pdf.status_code == 200
    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text() or ""
    assert code in text and "Konsultacja" in text
    assert (
        await client.get(f"/vouchers/{listed[0]['id']}/pdf?order_token={'q' * 20}")
    ).status_code == 404

    verified = await client.get(f"/vouchers/verify/{code.lower()}")
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] in {"active", "expiring_soon"} and "email" not in str(body)
    assert (await client.get("/vouchers/verify/NIEMA-KODU")).status_code == 404

    monkeypatch.setattr(voucher_router, "VERIFY_LIMIT_PER_MINUTE", 2)
    statuses = [(await client.get(f"/vouchers/verify/{code}")).status_code for _ in range(4)]
    assert 429 in statuses
