"""Admin product lifecycle: drafts, validation, publication, stock, files, chapters, images."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from reportlab.pdfgen import canvas
from sensoria.modules.library.models import EbookChapter, ProductFile
from sqlalchemy import select

from . import test_cart
from .admin_helpers import admin_headers, create_admin
from .test_cart import CartEnvironment
from .test_library import uploads

cart_environment = test_cart.cart_environment
__all__ = ["cart_environment", "uploads"]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _pdf() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 700, "x")
    pdf.save()
    return buffer.getvalue()


async def _login(client: AsyncClient, factory: Any, role: str = "staff") -> dict[str, str]:
    await create_admin(factory, f"{role}@example.com", role)
    return await admin_headers(client, f"{role}@example.com")


@pytest.mark.asyncio
async def test_book_draft_publish_price_reason_and_stock(
    cart_environment: CartEnvironment, uploads: Path
) -> None:
    client, factory = cart_environment
    h = await _login(client, factory)
    image = await client.post(
        "/admin/products/images", files={"file": ("a.png", PNG, "image/png")}, headers=h
    )
    assert image.status_code == 201
    url = image.json()["url"]
    served = await client.get(url.removeprefix("/api"))
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert "immutable" in served.headers["cache-control"]
    bad = await client.post(
        "/admin/products/images",
        files={"file": ("a.png", b"<svg onload=alert(1)>", "image/png")},
        headers=h,
    )
    assert bad.status_code == 422
    assert (await client.get("/media/..%2Fsecret.png")).status_code in {404, 422}

    created = await client.post(
        "/admin/products",
        json={
            "kind": "BOOK",
            "name": "Świadoma seksualność",
            "price": 5900,
            "vat_rate": "RATE_5",
            "short_description": "Książka",
            "images": [{"url": url, "alt": "Okładka"}],
            "book": {
                "stock_quantity": 10,
                "low_stock_threshold": 2,
                "weight_grams": 320,
                "length_mm": 210,
                "width_mm": 148,
                "height_mm": 22,
            },
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["slug"] == "swiadoma-seksualnosc" and created.json()["status"] == "DRAFT"
    again = await client.post(
        "/admin/products", json={"kind": "BOOK", "name": "Świadoma seksualność"}, headers=h
    )
    assert again.json()["slug"] == "swiadoma-seksualnosc-2"

    no_reason = await client.patch(f"/admin/products/{pid}", json={"price": 6900}, headers=h)
    assert no_reason.status_code == 422
    patched = await client.patch(
        f"/admin/products/{pid}",
        json={
            "price": 6900,
            "price_change_reason": "Nowy cennik",
            "name": "Świadoma seksualność II",
        },
        headers=h,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["price"] == 6900 and patched.json()["slug"] == "swiadoma-seksualnosc"
    unknown = await client.patch(f"/admin/products/{pid}", json={"kind": "VOUCHER"}, headers=h)
    assert unknown.status_code == 422

    incomplete = await client.post(f"/admin/products/{again.json()['id']}/publish", headers=h)
    assert incomplete.status_code >= 400
    published = await client.post(f"/admin/products/{pid}/publish", headers=h)
    assert published.status_code == 200 and published.json()["status"] == "PUBLISHED"
    public = await client.get("/products/swiadoma-seksualnosc")
    assert public.status_code == 200

    key = {**h, "Idempotency-Key": "stock-12345678"}
    adjusted = await client.post(
        f"/admin/products/{pid}/stock", json={"change": -3, "note": "Inwentaryzacja"}, headers=key
    )
    assert adjusted.status_code == 200 and adjusted.json()["stock_quantity"] == 7
    replay = await client.post(
        f"/admin/products/{pid}/stock", json={"change": -3, "note": "Inwentaryzacja"}, headers=key
    )
    assert replay.json()["stock_quantity"] == 7  # same key never double-applies
    withdraw_staff = await client.post(f"/admin/products/{pid}/withdraw", headers=h)
    assert withdraw_staff.status_code == 403
    listing = (await client.get("/admin/products?q=swiadoma&status=PUBLISHED", headers=h)).json()
    assert listing["total"] == 1


@pytest.mark.asyncio
async def test_ebook_files_chapters_and_validation(
    cart_environment: CartEnvironment, uploads: Path
) -> None:
    client, factory = cart_environment
    h = await _login(client, factory)
    created = await client.post(
        "/admin/products",
        json={"kind": "DIGITAL", "name": "E-book", "price": 4900, "vat_rate": "RATE_5"},
        headers=h,
    )
    pid = created.json()["id"]
    fake = await client.post(
        f"/admin/products/{pid}/files",
        files={"file": ("book.pdf", b"MZ not a pdf", "application/pdf")},
        data={"label": "E-book"},
        headers=h,
    )
    assert fake.status_code == 422
    audio_on_ebook = await client.post(
        f"/admin/products/{pid}/files",
        files={"file": ("a.mp3", b"ID3" + b"\x00" * 100, "audio/mpeg")},
        data={"label": "Audio"},
        headers=h,
    )
    assert audio_on_ebook.status_code == 422
    uploaded = await client.post(
        f"/admin/products/{pid}/files",
        files={"file": ("book.pdf", _pdf(), "application/pdf")},
        data={"label": "E-book PDF"},
        headers=h,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert not list(uploads.rglob("book.pdf"))  # stored under a random name only

    chapters = await client.put(
        f"/admin/products/{pid}/chapters",
        json={
            "chapters": [
                {"title": "Wstęp", "page_count": 10, "blocks": [{"type": "p", "text": "Treść"}]},
                {
                    "title": "Ćwiczenie",
                    "blocks": [{"type": "exercise", "title": "Mapa", "items": ["Dotyk", "Dźwięk"]}],
                },
            ]
        },
        headers=h,
    )
    assert chapters.json() == {"count": 2}
    bad_block = await client.put(
        f"/admin/products/{pid}/chapters",
        json={"chapters": [{"title": "X", "blocks": [{"type": "script", "text": "alert(1)"}]}]},
        headers=h,
    )
    assert bad_block.status_code == 422
    detail = (await client.get(f"/admin/products/{pid}", headers=h)).json()
    assert len(detail["files"]) == 1 and len(detail["reader_chapters"]) == 2
    async with factory() as session:
        assert len((await session.scalars(select(EbookChapter))).all()) == 2
        assert len((await session.scalars(select(ProductFile))).all()) == 1

    owner = await _login(client, factory, "owner")
    removed = await client.delete(
        f"/admin/products/{pid}/files/{detail['files'][0]['id']}", headers=owner
    )
    assert removed.status_code == 204
