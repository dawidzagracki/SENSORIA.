"""Entitlements, protected download links, reader content and progress."""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.accounts.auth import digest_secret, require_customer_id
from sensoria.modules.catalog.models import Product, ProductAudiobook, ProductAudiobookChapter
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.orders.models import Order, OrderConsent, OrderItem
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.modules.storage.models import StoredFile
from sensoria.modules.storage.service import StorageService
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import (
    ContentProgress,
    DownloadLink,
    EbookChapter,
    Entitlement,
    ProductFile,
    WatermarkedFile,
)
from .watermark import stamp_pdf

LINK_TTL = timedelta(hours=24)
LINK_MAX_USES = 5
NOT_FOUND = DomainError("ENTITLEMENT_NOT_FOUND", "Nie znaleziono materiału.", 404)


async def grant_entitlements_for_paid_order(
    session: AsyncSession, order_id: UUID, *, now: datetime | None = None
) -> list[Entitlement]:
    """Create one entitlement per digital/audiobook line; idempotent, no commit."""
    granted_at = now or datetime.now(UTC)
    digital_consent = await session.scalar(
        select(OrderConsent.granted).where(
            OrderConsent.order_id == order_id, OrderConsent.kind == "digital"
        )
    )
    rows = (
        await session.execute(
            select(OrderItem, Product.kind)
            .join(Product, Product.id == OrderItem.product_id)
            .where(
                OrderItem.order_id == order_id,
                Product.kind.in_([ProductKind.DIGITAL, ProductKind.AUDIOBOOK]),
            )
            .order_by(OrderItem.id)
        )
    ).all()
    result: list[Entitlement] = []
    for item, kind in rows:
        existing = await session.scalar(
            select(Entitlement).where(Entitlement.order_item_id == item.id)
        )
        if existing is not None:
            result.append(existing)
            continue
        if digital_consent is not True:
            # Immediate release requires the recorded consent; fail closed without losing the order.
            session.add(
                AuditLog(
                    actor_type=ActorType.SYSTEM,
                    actor_id=None,
                    entity_type="order_item",
                    entity_id=item.id,
                    action="entitlement.withheld_no_consent",
                    payload={"order_id": str(order_id)},
                )
            )
            continue
        entitlement = Entitlement(
            order_id=order_id,
            order_item_id=item.id,
            product_id=item.product_id,
            kind="audiobook" if kind is ProductKind.AUDIOBOOK else "digital",
            granted_at=granted_at,
        )
        session.add(entitlement)
        result.append(entitlement)
    await session.flush()
    return result


async def authorize_entitlement(
    session: AsyncSession,
    request: Request,
    entitlement_id: UUID,
    order_token: str | None,
) -> tuple[Entitlement, Order]:
    """Guest order token or customer session; unknown and foreign ids look identical."""
    entitlement = await session.get(Entitlement, entitlement_id)
    order = await session.get(Order, entitlement.order_id) if entitlement else None
    if entitlement is None or order is None:
        if order_token is None:
            await require_customer_id(request, session)
        raise NOT_FOUND
    if order_token is not None:
        if not verify_order_access_token(order.id, order_token):
            raise NOT_FOUND
    else:
        customer_id = await require_customer_id(request, session)
        if order.customer_id != customer_id:
            raise NOT_FOUND
    if entitlement.status != "active" or order.status != "paid":
        raise DomainError("ENTITLEMENT_REVOKED", "Dostęp do materiału jest wyłączony.", 403)
    return entitlement, order


async def _product_files(session: AsyncSession, product_id: UUID) -> list[ProductFile]:
    return list(
        (
            await session.scalars(
                select(ProductFile)
                .where(ProductFile.product_id == product_id)
                .order_by(ProductFile.position, ProductFile.id)
            )
        ).all()
    )


async def entitlement_detail(
    session: AsyncSession, entitlement: Entitlement, order: Order
) -> dict[str, Any]:
    product = await session.get(Product, entitlement.product_id)
    assert product is not None
    files = await _product_files(session, product.id)
    chapters = list(
        (
            await session.scalars(
                select(EbookChapter)
                .where(EbookChapter.product_id == product.id)
                .order_by(EbookChapter.position)
            )
        ).all()
    )
    audio_chapters = list(
        (
            await session.scalars(
                select(ProductAudiobookChapter)
                .where(ProductAudiobookChapter.audiobook_id == product.id)
                .order_by(ProductAudiobookChapter.position)
            )
        ).all()
    )
    audiobook = await session.get(ProductAudiobook, product.id)
    progress = await session.get(ContentProgress, entitlement.id)
    total_pages = sum(chapter.page_count or 0 for chapter in chapters)
    return {
        "id": entitlement.id,
        "kind": entitlement.kind,
        "product_id": product.id,
        "title": product.name,
        "author": audiobook.narrator if audiobook else None,
        "order_number": order.public_number,
        "buyer_email": order.email,
        "granted_at": entitlement.granted_at,
        "files": [
            {"id": f.id, "kind": f.kind, "label": f.label, "chapter_id": f.chapter_id}
            for f in files
        ],
        "reader_chapters": [
            {"position": c.position, "title": c.title, "page_count": c.page_count} for c in chapters
        ],
        "audio_chapters": [
            {
                "position": c.position,
                "title": c.title,
                "length_seconds": c.length_seconds,
                "file_id": next((f.id for f in files if f.chapter_id == c.id), None),
            }
            for c in audio_chapters
        ],
        "total_pages": total_pages or None,
        "progress": {
            "position": progress.position if progress else 0,
            "offset_seconds": progress.offset_seconds if progress else 0,
            "completed": progress.completed if progress else [],
            "font_scale": progress.font_scale if progress else 100,
        },
    }


async def issue_download_link(
    session: AsyncSession, entitlement: Entitlement, file_id: UUID
) -> tuple[str, DownloadLink]:
    """Revoke earlier live links for the file and mint a fresh limited one (renewal)."""
    product_file = await session.get(ProductFile, file_id)
    if product_file is None or product_file.product_id != entitlement.product_id:
        raise DomainError("FILE_NOT_FOUND", "Nie znaleziono pliku.", 404)
    now = datetime.now(UTC)
    await session.execute(
        update(DownloadLink)
        .where(
            DownloadLink.entitlement_id == entitlement.id,
            DownloadLink.product_file_id == file_id,
            DownloadLink.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = secrets.token_urlsafe(32)
    link = DownloadLink(
        token_hash=digest_secret("download:" + token),
        entitlement_id=entitlement.id,
        product_file_id=file_id,
        expires_at=now + LINK_TTL,
        max_uses=LINK_MAX_USES,
    )
    session.add(link)
    await session.flush()
    return token, link


async def _ensure_watermarked(
    session: AsyncSession, entitlement: Entitlement, product_file: ProductFile
) -> StoredFile:
    cached = await session.scalar(
        select(WatermarkedFile).where(
            WatermarkedFile.entitlement_id == entitlement.id,
            WatermarkedFile.product_file_id == product_file.id,
        )
    )
    if cached is not None:
        stored = await session.get(StoredFile, cached.stored_file_id)
        assert stored is not None
        return stored
    order = await session.get(Order, entitlement.order_id)
    source = await session.get(StoredFile, product_file.stored_file_id)
    assert order is not None and source is not None
    storage = StorageService()
    path = storage.resolve_file(source)
    stamped = await asyncio.to_thread(
        lambda: stamp_pdf(
            path.read_bytes(), email=order.email, order_number=order.public_number or str(order.id)
        )
    )
    stored = await storage.store_file(
        session,
        category="watermarked",
        scope_id=entitlement.id,
        year=datetime.now(UTC).year,
        content=stamped,
        original_name=f"{product_file.label}.pdf",
        mime_type="application/pdf",
    )
    session.add(
        WatermarkedFile(
            entitlement_id=entitlement.id,
            product_file_id=product_file.id,
            stored_file_id=stored.id,
        )
    )
    await session.flush()
    return stored


async def prepare_file_for_entitlement(
    session: AsyncSession, entitlement: Entitlement, product_file: ProductFile
) -> tuple[StoredFile, str, str]:
    """Return (stored file, media type, download name); PDFs are always buyer-stamped."""
    if product_file.kind == "pdf":
        stored = await _ensure_watermarked(session, entitlement, product_file)
        return stored, "application/pdf", f"{_safe_name(product_file.label)}.pdf"
    audio = await session.get(StoredFile, product_file.stored_file_id)
    assert audio is not None
    return audio, audio.mime_type, f"{_safe_name(product_file.label)}.mp3"


def _safe_name(label: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_ " else "_" for c in label).strip()
    return (cleaned or "plik")[:80]


async def redeem_download_link(
    session: AsyncSession, token: str, *, counts_as_use: bool
) -> tuple[Entitlement, ProductFile]:
    """Validate a link and consume one use atomically."""
    gone = DomainError(
        "DOWNLOAD_LINK_INVALID",
        "Link wygasł lub został wykorzystany. Wygeneruj nowy w swojej bibliotece.",
        410,
    )
    link = await session.scalar(
        select(DownloadLink)
        .where(DownloadLink.token_hash == digest_secret("download:" + token))
        .with_for_update()
    )
    if link is None:
        raise gone
    now = datetime.now(UTC)
    if link.revoked_at is not None or link.expires_at <= now or link.use_count >= link.max_uses:
        raise gone
    entitlement = await session.get(Entitlement, link.entitlement_id)
    product_file = await session.get(ProductFile, link.product_file_id)
    order = await session.get(Order, entitlement.order_id) if entitlement else None
    if (
        entitlement is None
        or product_file is None
        or order is None
        or entitlement.status != "active"
        or order.status != "paid"
    ):
        raise gone
    if counts_as_use:
        link.use_count += 1
        await session.flush()
    return entitlement, product_file


async def customer_library(session: AsyncSession, customer_id: UUID) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Entitlement, Order, Product)
            .join(Order, Order.id == Entitlement.order_id)
            .join(Product, Product.id == Entitlement.product_id)
            .where(
                Order.customer_id == customer_id,
                Order.status == "paid",
                Entitlement.status == "active",
            )
            .order_by(Entitlement.granted_at.desc(), Entitlement.id)
        )
    ).all()
    items: list[dict[str, Any]] = []
    for entitlement, order, product in rows:
        progress = await session.get(ContentProgress, entitlement.id)
        chapters = list(
            (
                await session.scalars(
                    select(EbookChapter).where(EbookChapter.product_id == product.id)
                )
            ).all()
        )
        items.append(
            {
                "id": entitlement.id,
                "kind": entitlement.kind,
                "title": product.name,
                "order_number": order.public_number,
                "granted_at": entitlement.granted_at,
                "has_reader": bool(chapters),
                "chapters_total": len(chapters),
                "chapters_completed": len(progress.completed) if progress else 0,
            }
        )
    return items


async def order_library(session: AsyncSession, order: Order) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Entitlement, Product)
            .join(Product, Product.id == Entitlement.product_id)
            .where(Entitlement.order_id == order.id, Entitlement.status == "active")
            .order_by(Entitlement.id)
        )
    ).all()
    return [
        {
            "id": e.id,
            "kind": e.kind,
            "title": p.name,
            "order_number": order.public_number,
            "granted_at": e.granted_at,
            "has_reader": False,
            "chapters_total": 0,
            "chapters_completed": 0,
        }
        for e, p in rows
    ]


async def read_chapter(
    session: AsyncSession, entitlement: Entitlement, position: int
) -> EbookChapter:
    chapter = await session.scalar(
        select(EbookChapter).where(
            EbookChapter.product_id == entitlement.product_id, EbookChapter.position == position
        )
    )
    if chapter is None:
        raise DomainError("CHAPTER_NOT_FOUND", "Nie znaleziono rozdziału.", 404)
    return chapter


async def save_progress(
    session: AsyncSession,
    entitlement: Entitlement,
    *,
    position: int,
    offset_seconds: int,
    completed_position: int | None,
    font_scale: int | None,
) -> ContentProgress:
    row = await session.get(ContentProgress, entitlement.id, with_for_update=True)
    if row is None:
        row = ContentProgress(
            entitlement_id=entitlement.id,
            position=0,
            offset_seconds=0,
            completed=[],
            font_scale=100,
        )
        session.add(row)
    row.position = position
    row.offset_seconds = offset_seconds
    if font_scale is not None:
        row.font_scale = font_scale
    if completed_position is not None and completed_position not in row.completed:
        row.completed = sorted([*row.completed, completed_position])
    await session.flush()
    return row
