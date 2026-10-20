"""Entitlements, watermarked downloads, link limits, reader and audio streaming."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sensoria.config import Settings, get_settings
from sensoria.modules.catalog.models import ProductAudiobook, ProductAudiobookChapter
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.library.models import (
    DownloadLink,
    EbookChapter,
    Entitlement,
    ProductFile,
)
from sensoria.modules.library.streaming import parse_range
from sensoria.modules.storage.service import StorageService
from sensoria.shared.errors import DomainError
from sqlalchemy import select, update

from . import test_cart
from .test_cart import CartEnvironment
from .test_payments import _checkout, _event, _post_event, stripe_settings

cart_environment = test_cart.cart_environment
__all__ = ["stripe_settings", "cart_environment"]


def _pdf(pages: int = 2) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for number in range(pages):
        pdf.drawString(72, 700, f"Strona {number + 1}")
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "UPLOADS_ROOT", str(tmp_path))
    return tmp_path


async def _pay(client: AsyncClient, checkout: dict[str, Any], factory: Any) -> None:
    from sensoria.modules.payments.models import Payment

    order_id, token = checkout["order_id"], checkout["access_token"]
    assert (
        await client.post(f"/payments/orders/{order_id}/session?token={token}")
    ).status_code == 200
    async with factory() as session:
        sid = (await session.scalar(select(Payment.provider_session_id))) or ""
    paid = await _post_event(
        client,
        _event(
            "checkout.session.completed",
            sid,
            payment_status="paid",
            amount_total=checkout["amount_due_grosz"],
            currency="pln",
        ),
    )
    assert paid.json()["outcome"] == "paid"


async def _attach_pdf(factory: Any, product_id: UUID) -> None:
    async with factory() as session, session.begin():
        stored = await StorageService().store_file(
            session,
            category="products",
            scope_id=product_id,
            year=2026,
            content=_pdf(),
            original_name="ebook.pdf",
            mime_type="application/pdf",
        )
        session.add(
            ProductFile(product_id=product_id, stored_file_id=stored.id, kind="pdf", label="E-book")
        )
        session.add(
            EbookChapter(
                product_id=product_id,
                position=0,
                title="Wstęp",
                page_count=10,
                blocks=[{"type": "p", "text": "Treść <b>bezpieczna</b>"}],
            )
        )


@pytest.mark.asyncio
async def test_paid_ebook_gets_entitlement_and_stamped_pdf_with_link_limits(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    async with factory() as session:
        from sensoria.modules.orders.models import OrderItem

        product_id = (await session.scalar(select(OrderItem.product_id))) or UUID(int=0)
    await _attach_pdf(factory, product_id)
    await _pay(client, checkout, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]

    library = await client.get(f"/library/orders/{order_id}?order_token={token}")
    assert library.status_code == 200
    items = library.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "digital"
    ent_id = items[0]["id"]

    assert (await client.get(f"/library/entitlements/{ent_id}")).status_code == 401
    wrong = await client.get(f"/library/entitlements/{ent_id}?order_token={'a' * 20}")
    assert wrong.status_code == 404
    detail = await client.get(f"/library/entitlements/{ent_id}?order_token={token}")
    assert detail.status_code == 200
    file_id = detail.json()["files"][0]["id"]

    link = await client.post(
        f"/library/entitlements/{ent_id}/download-links?order_token={token}",
        json={"file_id": file_id},
    )
    assert link.status_code == 200 and link.json()["uses_left"] == 5
    url = link.json()["url"].removeprefix("/api")
    first = await client.get(url)
    assert first.status_code == 200
    assert first.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(first.content))
    assert len(reader.pages) == 2
    assert "buyer@example.com" in (reader.pages[0].extract_text() or "")
    assert reader.metadata is not None
    assert "buyer@example.com" in str(reader.metadata.get("/Subject"))

    # Renewal revokes the previous link and a link is exhausted after its uses.
    renewed = await client.post(
        f"/library/entitlements/{ent_id}/download-links?order_token={token}",
        json={"file_id": file_id},
    )
    assert (await client.get(url)).status_code == 410
    new_url = renewed.json()["url"].removeprefix("/api")
    for _ in range(5):
        assert (await client.get(new_url)).status_code == 200
    assert (await client.get(new_url)).status_code == 410

    async with factory() as session:
        await session.execute(update(DownloadLink).values(use_count=0, revoked_at=None))
        await session.commit()
        link_row = await session.scalar(select(DownloadLink).limit(1))
        assert link_row is not None
        await session.execute(update(DownloadLink).values(expires_at=link_row.created_at))
        await session.commit()
    assert (await client.get(new_url)).status_code == 410

    chapter = await client.get(f"/library/entitlements/{ent_id}/chapters/0?order_token={token}")
    assert chapter.status_code == 200
    body = chapter.json()
    assert body["blocks"][0]["text"] == "Treść <b>bezpieczna</b>"  # data, rendered as text
    assert "buyer@example.com" in body["footer"] and body["total_chapters"] == 1
    assert (
        await client.get(f"/library/entitlements/{ent_id}/chapters/5?order_token={token}")
    ).status_code == 404

    saved = await client.put(
        f"/library/entitlements/{ent_id}/progress?order_token={token}",
        json={"position": 0, "completed_position": 0, "font_scale": 120},
    )
    assert saved.status_code == 204
    again = (await client.get(f"/library/entitlements/{ent_id}?order_token={token}")).json()
    assert again["progress"]["completed"] == [0] and again["progress"]["font_scale"] == 120


@pytest.mark.asyncio
async def test_unpaid_order_has_no_entitlement_and_revocation_blocks_access(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    checkout = await _checkout(client, ProductKind.DIGITAL, factory)
    order_id, token = checkout["order_id"], checkout["access_token"]
    unpaid = await client.get(f"/library/orders/{order_id}?order_token={token}")
    assert unpaid.json()["items"] == []
    await _pay(client, checkout, factory)
    async with factory() as session:
        ent = await session.scalar(select(Entitlement))
        assert ent is not None
        ent_id = ent.id
        ent.status = "revoked"
        await session.commit()
    blocked = await client.get(f"/library/entitlements/{ent_id}?order_token={token}")
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_audiobook_streams_with_range(
    cart_environment: CartEnvironment, stripe_settings: Settings
) -> None:
    client, factory = cart_environment
    from sensoria.shared.types import VatRate

    from .test_cart import _product

    audio = _product(ProductKind.AUDIOBOOK, price=7900, vat_rate=VatRate.RATE_5)
    audio.audiobook = ProductAudiobook(
        duration_seconds=60,
        narrator="Autorka",
        chapters=[ProductAudiobookChapter(title="Rozdział", length_seconds=60, position=0)],
    )
    checkout = await _checkout(client, ProductKind.AUDIOBOOK, factory, product=audio)
    async with factory() as session:
        from sensoria.modules.orders.models import OrderItem

        product_id = (await session.scalar(select(OrderItem.product_id))) or UUID(int=0)
    async with factory() as session, session.begin():
        chapter = await session.scalar(
            select(ProductAudiobookChapter).where(
                ProductAudiobookChapter.audiobook_id == product_id
            )
        )
        assert chapter is not None
        stored = await StorageService().store_file(
            session,
            category="products",
            scope_id=product_id,
            year=2026,
            content=bytes(range(256)) * 8,
            original_name="r1.mp3",
            mime_type="audio/mpeg",
        )
        session.add(
            ProductFile(
                product_id=product_id,
                stored_file_id=stored.id,
                kind="audio",
                label="Rozdział 1",
                chapter_id=chapter.id,
            )
        )
    await _pay(client, checkout, factory)
    token = checkout["access_token"]
    items = (
        await client.get(f"/library/orders/{checkout['order_id']}?order_token={token}")
    ).json()["items"]
    ent_id = items[0]["id"]
    detail = (await client.get(f"/library/entitlements/{ent_id}?order_token={token}")).json()
    file_id = detail["audio_chapters"][0]["file_id"]
    assert file_id
    url = f"/library/entitlements/{ent_id}/audio/{file_id}?order_token={token}"
    part = await client.get(url, headers={"Range": "bytes=10-19"})
    assert part.status_code == 206
    assert part.content == bytes(range(10, 20))
    assert part.headers["content-range"] == "bytes 10-19/2048"
    assert (await client.get(url, headers={"Range": "bytes=9999-"})).status_code == 416
    assert (await client.get(url)).status_code == 200


def test_range_parser() -> None:
    assert parse_range(None, 100) == (0, 99, False)
    assert parse_range("bytes=-10", 100) == (90, 99, True)
    assert parse_range("bytes=5-", 100) == (5, 99, True)
    for bad in ("bytes=0-1,5-6", "bytes=-", "items=1-2", "bytes=100-"):
        with pytest.raises(DomainError):
            parse_range(bad, 100)
