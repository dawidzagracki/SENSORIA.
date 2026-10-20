"""Product management: drafts, publication, prices, stock, images, files and reader chapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload

from sensoria.modules.catalog.inventory import append_stock_movement
from sensoria.modules.catalog.media import MAX_IMAGE_BYTES, store_image
from sensoria.modules.catalog.models import (
    Product,
    ProductAudiobook,
    ProductAudiobookChapter,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
)
from sensoria.modules.catalog.price_history import price_change_context
from sensoria.modules.catalog.schemas import ProductDraftInput
from sensoria.modules.catalog.service import publish_product, slug_exists
from sensoria.modules.catalog.slug import slugify
from sensoria.modules.catalog.types import ProductKind, ProductStatus
from sensoria.modules.library.models import EbookChapter, ProductFile
from sensoria.modules.storage.service import StorageService
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate

from .common import Owner, Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/products", tags=["admin-products"])
MAX_PDF_BYTES = 200 * 1024 * 1024
MAX_AUDIO_BYTES = 500 * 1024 * 1024
ALL_LOADS = (
    selectinload(Product.images),
    selectinload(Product.voucher).selectinload(ProductVoucher.variants),
    selectinload(Product.book),
    selectinload(Product.audiobook).selectinload(ProductAudiobook.chapters),
    selectinload(Product.digital),
)


class ProductPatch(BaseModel):
    """Partial edit; fields left out are untouched and kind cannot change."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    meta_title: str | None = Field(default=None, max_length=200)
    meta_description: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=2048)
    price: StrictInt | None = Field(default=None, ge=0)
    compare_at_price: StrictInt | None = Field(default=None, ge=0)
    vat_rate: VatRate | None = None
    sort_order: int | None = None
    images: list[dict[str, Any]] | None = None
    service_name: str | None = Field(default=None, max_length=200)
    validity_months: int | None = Field(default=None, gt=0, le=60)
    variant_prices: dict[str, StrictInt] | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)
    isbn: str | None = Field(default=None, max_length=20)
    binding: str | None = Field(default=None, max_length=80)
    weight_grams: int | None = Field(default=None, gt=0)
    narrator: str | None = Field(default=None, max_length=200)
    page_count: int | None = Field(default=None, gt=0)
    edition: str | None = Field(default=None, max_length=100)
    price_change_reason: str | None = Field(default=None, min_length=3, max_length=500)


class StockAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change: StrictInt
    note: str = Field(min_length=3, max_length=500)


class ChapterBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["p", "h2", "quote", "list", "exercise"]
    text: str | None = Field(default=None, max_length=8000)
    title: str | None = Field(default=None, max_length=200)
    items: list[str] | None = Field(default=None, max_length=50)

    @field_validator("items")
    @classmethod
    def item_length(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(len(item) > 1000 for item in value):
            raise ValueError("Element listy jest zbyt długi.")
        return value


class ChapterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    page_count: int | None = Field(default=None, gt=0, le=2000)
    blocks: list[ChapterBlock] = Field(min_length=1, max_length=500)


class ChaptersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapters: list[ChapterInput] = Field(max_length=100)


def _summary(p: Product) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "kind": p.kind.value,
        "name": p.name,
        "slug": p.slug,
        "status": p.status.value,
        "price": p.price,
        "compare_at_price": p.compare_at_price,
        "vat_rate": p.vat_rate.value if p.vat_rate else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "sort_order": p.sort_order,
    }


async def _load(session: SessionDependency, product_id: UUID, *, lock: bool = False) -> Product:
    statement = select(Product).where(Product.id == product_id).options(*ALL_LOADS)
    if lock:
        statement = statement.with_for_update(of=Product)
    product = await session.scalar(statement)
    if product is None:
        raise DomainError("PRODUCT_NOT_FOUND", "Nie znaleziono produktu.", 404)
    return product


async def _unique_slug(session: SessionDependency, name: str) -> str:
    base = slugify(name) or "produkt"
    candidate, counter = base, 1
    while await slug_exists(session, candidate):
        counter += 1
        candidate = f"{base}-{counter}"
    return candidate


def _detail(p: Product) -> dict[str, Any]:
    out = _summary(p)
    out.update(
        short_description=p.short_description,
        description=p.description,
        meta_title=p.meta_title,
        meta_description=p.meta_description,
        og_image=p.og_image,
        images=[{"url": i.url, "alt": i.alt, "position": i.position} for i in p.images],
    )
    if p.voucher:
        out["voucher"] = {
            "service_name": p.voucher.service_name,
            "validity_months": p.voucher.validity_months,
            "variants": [{"kind": v.kind.value, "price": v.price} for v in p.voucher.variants],
        }
    if p.book:
        out["book"] = {
            "stock_quantity": p.book.stock_quantity,
            "low_stock_threshold": p.book.low_stock_threshold,
            "weight_grams": p.book.weight_grams,
            "isbn": p.book.isbn,
            "binding": p.book.binding,
        }
    if p.audiobook:
        out["audiobook"] = {
            "duration_seconds": p.audiobook.duration_seconds,
            "narrator": p.audiobook.narrator,
            "chapters": [
                {"position": c.position, "title": c.title, "length_seconds": c.length_seconds}
                for c in p.audiobook.chapters
            ],
        }
    if p.digital:
        out["digital"] = {
            "page_count": p.digital.page_count,
            "edition": p.digital.edition,
            "label": p.digital.label.value,
        }
    return out


@router.get("")
async def list_products(
    session: SessionDependency,
    _admin: Staff,
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: Annotated[str | None, Query(pattern="^(VOUCHER|BOOK|AUDIOBOOK|DIGITAL)$")] = None,
    status: Annotated[str | None, Query(pattern="^(DRAFT|PUBLISHED|WITHDRAWN)$")] = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    statement = select(Product)
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(func.lower(Product.name).like(needle), func.lower(Product.slug).like(needle))
        )
    if kind:
        statement = statement.where(Product.kind == ProductKind(kind))
    if status:
        statement = statement.where(Product.status == ProductStatus(status))
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                statement.order_by(Product.created_at.desc(), Product.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
    )
    return {"total": total, "page": page, "items": [_summary(p) for p in rows]}


@router.get("/{product_id}")
async def get_product(
    product_id: UUID, session: SessionDependency, _admin: Staff
) -> dict[str, Any]:
    product = await _load(session, product_id)
    files = list(
        (
            await session.scalars(
                select(ProductFile)
                .where(ProductFile.product_id == product_id)
                .order_by(ProductFile.position, ProductFile.id)
            )
        ).all()
    )
    chapters = list(
        (
            await session.scalars(
                select(EbookChapter)
                .where(EbookChapter.product_id == product_id)
                .order_by(EbookChapter.position)
            )
        ).all()
    )
    return {
        **_detail(product),
        "files": [
            {"id": str(f.id), "kind": f.kind, "label": f.label, "position": f.position}
            for f in files
        ],
        "reader_chapters": [
            {"position": c.position, "title": c.title, "page_count": c.page_count} for c in chapters
        ],
    }


@router.post("", status_code=201)
async def create_product(
    payload: ProductDraftInput, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        product = Product(
            kind=payload.kind,
            name=payload.name.strip(),
            slug=await _unique_slug(session, payload.slug or payload.name or "produkt"),
            short_description=payload.short_description,
            description=payload.description,
            meta_title=payload.meta_title,
            meta_description=payload.meta_description,
            og_image=payload.og_image,
            price=payload.price,
            compare_at_price=payload.compare_at_price,
            vat_rate=payload.vat_rate,
            sort_order=payload.sort_order,
            status=ProductStatus.DRAFT,
            images=[
                ProductImage(url=i.url, alt=i.alt, position=i.position or idx)
                for idx, i in enumerate(payload.images)
            ],
            voucher=None,
            book=None,
            audiobook=None,
            digital=None,
            categories=[],
            audience_tags=[],
        )
        opening_stock = 0
        if payload.voucher is not None:
            product.voucher = ProductVoucher(
                validity_months=payload.voucher.validity_months,
                service_name=payload.voucher.service_name,
                variants=[
                    ProductVoucherVariant(kind=v.kind, price=v.price)
                    for v in payload.voucher.variants
                ],
            )
        if payload.book is not None:
            b = payload.book
            opening_stock = b.stock_quantity
            product.book = ProductBook(
                stock_quantity=0,
                low_stock_threshold=b.low_stock_threshold,
                weight_grams=b.weight_grams,
                length_mm=b.length_mm,
                width_mm=b.width_mm,
                height_mm=b.height_mm,
                isbn=b.isbn,
                binding=b.binding,
                shipping_business_days=b.shipping_business_days,
                shipping_method=b.shipping_method,
            )
        if payload.audiobook is not None:
            a = payload.audiobook
            product.audiobook = ProductAudiobook(
                duration_seconds=a.duration_seconds,
                narrator=a.narrator,
                file_format=a.file_format,
                chapters=[
                    ProductAudiobookChapter(
                        title=c.title, length_seconds=c.length_seconds, position=c.position
                    )
                    for c in a.chapters
                ],
            )
        if payload.digital is not None:
            d = payload.digital
            product.digital = ProductDigital(
                page_count=d.page_count,
                file_format=d.file_format,
                edition=d.edition,
                label=d.label,
            )
        async with price_change_context(
            session, actor_type=ActorType.ADMINISTRATOR, actor_id=admin.id, reason="Utworzenie"
        ):
            session.add(product)
            await session.flush()
        if opening_stock:
            await append_stock_movement(
                session,
                product_id=product.id,
                change=opening_stock,
                reason="correction",
                operation_key=f"opening:{product.id}",
                actor_id=admin.id,
                actor_type=ActorType.ADMINISTRATOR,
                note="Stan otwarcia przy tworzeniu produktu.",
            )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product.id,
                action="product.created",
                payload={"kind": product.kind.value},
            )
        )
        return {"id": str(product.id), "slug": product.slug, "status": product.status.value}


@router.patch("/{product_id}")
async def patch_product(
    product_id: UUID, payload: ProductPatch, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    fields = payload.model_fields_set
    async with session.begin():
        product = await _load(session, product_id, lock=True)
        if product.status is ProductStatus.WITHDRAWN:
            raise DomainError("PRODUCT_WITHDRAWN", "Wycofanego produktu nie można edytować.", 409)
        for name in (
            "name",
            "short_description",
            "description",
            "meta_title",
            "meta_description",
            "og_image",
            "sort_order",
        ):
            if name in fields:
                value = getattr(payload, name)
                setattr(product, name, value.strip() if isinstance(value, str) else value)
        if "images" in fields and payload.images is not None:
            product.images[:] = [
                ProductImage(
                    url=str(i.get("url", ""))[:2048],
                    alt=str(i.get("alt", ""))[:500],
                    position=idx,
                )
                for idx, i in enumerate(payload.images)
            ]
        price_fields = {"price", "compare_at_price", "vat_rate"} & fields
        if price_fields:
            if not payload.price_change_reason:
                raise DomainError(
                    "PRICE_REASON_REQUIRED", "Zmiana ceny lub VAT wymaga podania powodu.", 422
                )
            async with price_change_context(
                session,
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                reason=payload.price_change_reason,
            ):
                for name in price_fields:
                    setattr(product, name, getattr(payload, name))
                await session.flush()
        if product.voucher:
            if "service_name" in fields and payload.service_name is not None:
                product.voucher.service_name = payload.service_name.strip()
            if "validity_months" in fields and payload.validity_months is not None:
                product.voucher.validity_months = payload.validity_months
            if payload.variant_prices:
                reason = payload.price_change_reason or "Zmiana ceny wariantu"
                async with price_change_context(
                    session,
                    actor_type=ActorType.ADMINISTRATOR,
                    actor_id=admin.id,
                    reason=reason,
                ):
                    for variant in product.voucher.variants:
                        if variant.kind.value in payload.variant_prices:
                            variant.price = payload.variant_prices[variant.kind.value]
                    await session.flush()
        if product.book:
            for name in ("low_stock_threshold", "isbn", "binding", "weight_grams"):
                if name in fields:
                    setattr(product.book, name, getattr(payload, name))
        if product.audiobook and "narrator" in fields:
            product.audiobook.narrator = payload.narrator
        if product.digital:
            for name in ("page_count", "edition"):
                if name in fields:
                    setattr(product.digital, name, getattr(payload, name))
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product.id,
                action="product.updated",
                payload={"fields": sorted(fields)},
            )
        )
        await session.flush()
    return _detail(await _load(session, product_id))


@router.post("/{product_id}/publish")
async def publish(product_id: UUID, session: SessionDependency, admin: Staff) -> dict[str, Any]:
    async with session.begin():
        product = await _load(session, product_id, lock=True)
        await publish_product(session, product)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product.id,
                action="product.published",
                payload={},
            )
        )
    return _summary(await _load(session, product_id))


@router.post("/{product_id}/withdraw")
async def withdraw(product_id: UUID, session: SessionDependency, admin: Owner) -> dict[str, Any]:
    async with session.begin():
        product = await _load(session, product_id, lock=True)
        product.status = ProductStatus.WITHDRAWN
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product.id,
                action="product.withdrawn",
                payload={},
            )
        )
    return _summary(await _load(session, product_id))


@router.post("/{product_id}/stock")
async def adjust_stock(
    product_id: UUID,
    payload: StockAdjustment,
    session: SessionDependency,
    admin: Staff,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> dict[str, Any]:
    async with session.begin():
        product = await _load(session, product_id)
        if product.kind is not ProductKind.BOOK or product.book is None:
            raise DomainError("STOCK_NOT_BOOK", "Stan dotyczy wyłącznie książek.", 422)
        movement = await append_stock_movement(
            session,
            product_id=product_id,
            change=payload.change,
            reason="manual_adjustment",
            operation_key=f"admin:{product_id}:{idempotency_key}",
            actor_id=admin.id,
            actor_type=ActorType.ADMINISTRATOR,
            note=payload.note,
        )
        await session.flush()
        stock = await session.scalar(
            select(ProductBook.stock_quantity)
            .where(ProductBook.product_id == product_id)
            .execution_options(populate_existing=True)
        )
    return {"movement_id": str(movement.id), "stock_quantity": stock}


@router.post("/images", status_code=201)
async def upload_image(_admin: Staff, file: Annotated[UploadFile, File()]) -> dict[str, str]:
    """Store a product image publicly under a random name; type is detected from content."""
    content = await file.read(MAX_IMAGE_BYTES + 1)
    name = store_image(content)
    return {"url": f"/api/media/{name}"}


async def _require_readable_pdf(content: bytes) -> None:
    """Reject corrupt or password-protected PDFs now, not when the first buyer downloads."""
    import asyncio
    import io

    from pypdf import PdfReader

    def check() -> None:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError("encrypted")
        if len(reader.pages) < 1:
            raise ValueError("empty")
        reader.pages[0].extract_text()

    try:
        await asyncio.to_thread(check)
    except Exception:
        raise DomainError(
            "FILE_PDF_UNREADABLE",
            "Nie można odczytać tego PDF-a. Plik jest uszkodzony lub zabezpieczony hasłem.",
            422,
        ) from None


def _looks_like_mp3(head: bytes) -> bool:
    return head.startswith(b"ID3") or (len(head) > 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)


@router.post("/{product_id}/files", status_code=201)
async def upload_file(
    product_id: UUID,
    session: SessionDependency,
    admin: Staff,
    file: Annotated[UploadFile, File()],
    label: Annotated[str, Form(min_length=1, max_length=200)],
    chapter_position: Annotated[int | None, Form(ge=0)] = None,
) -> dict[str, Any]:
    """Attach the paid full-length file; content is verified by magic bytes, never by name."""
    limit = MAX_PDF_BYTES
    head = await file.read(16)
    if head.startswith(b"%PDF-"):
        kind, mime = "pdf", "application/pdf"
    elif _looks_like_mp3(head):
        kind, mime, limit = "audio", "audio/mpeg", MAX_AUDIO_BYTES
    else:
        raise DomainError("FILE_TYPE_INVALID", "Dozwolone są wyłącznie pliki PDF oraz MP3.", 422)
    body = head + await file.read(limit + 1)
    if len(body) > limit:
        raise DomainError("FILE_TOO_LARGE", "Plik przekracza dozwolony rozmiar.", 413)
    if kind == "pdf":
        await _require_readable_pdf(body)
    async with session.begin():
        product = await _load(session, product_id)
        expected = {ProductKind.DIGITAL: "pdf", ProductKind.AUDIOBOOK: "audio"}.get(product.kind)
        if expected != kind:
            raise DomainError(
                "FILE_KIND_MISMATCH", "Typ pliku nie pasuje do rodzaju produktu.", 422
            )
        chapter_id: UUID | None = None
        position = int(
            await session.scalar(
                select(func.coalesce(func.max(ProductFile.position) + 1, 0)).where(
                    ProductFile.product_id == product_id
                )
            )
            or 0
        )
        if kind == "audio" and chapter_position is not None and product.audiobook is not None:
            chapter = next(
                (c for c in product.audiobook.chapters if c.position == chapter_position), None
            )
            if chapter is None:
                raise DomainError("CHAPTER_NOT_FOUND", "Nie znaleziono rozdziału audiobooka.", 404)
            chapter_id, position = chapter.id, chapter.position
        stored = await StorageService().store_file(
            session,
            category="products",
            scope_id=product_id,
            year=datetime.now(UTC).year,
            content=body,
            original_name=(file.filename or "plik")[:255],
            mime_type=mime,
        )
        record = ProductFile(
            product_id=product_id,
            stored_file_id=stored.id,
            kind=kind,
            label=label.strip(),
            position=position,
            chapter_id=chapter_id,
        )
        session.add(record)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product_id,
                action="product.file_uploaded",
                payload={"kind": kind, "size_bytes": len(body)},
            )
        )
        await session.flush()
        return {"id": str(record.id), "kind": kind, "size_bytes": len(body)}


@router.delete("/{product_id}/files/{file_id}", status_code=204)
async def delete_file(
    product_id: UUID, file_id: UUID, session: SessionDependency, admin: Owner
) -> None:
    async with session.begin():
        record = await session.scalar(
            select(ProductFile).where(
                ProductFile.id == file_id, ProductFile.product_id == product_id
            )
        )
        if record is None:
            raise DomainError("FILE_NOT_FOUND", "Nie znaleziono pliku.", 404)
        stored_id = record.stored_file_id
        await session.delete(record)
        await session.flush()
        # Keep bytes on disk and the metadata row: buyers' watermarked copies reference history.
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="stored_file",
                entity_id=stored_id,
                action="product.file_detached",
                payload={"product_id": str(product_id)},
            )
        )


@router.put("/{product_id}/chapters")
async def replace_chapters(
    product_id: UUID, payload: ChaptersInput, session: SessionDependency, admin: Staff
) -> dict[str, int]:
    async with session.begin():
        product = await _load(session, product_id)
        if product.kind is not ProductKind.DIGITAL:
            raise DomainError("CHAPTERS_NOT_DIGITAL", "Rozdziały dotyczą e-booków.", 422)
        await session.execute(delete(EbookChapter).where(EbookChapter.product_id == product_id))
        for position, chapter in enumerate(payload.chapters):
            session.add(
                EbookChapter(
                    product_id=product_id,
                    position=position,
                    title=chapter.title.strip(),
                    page_count=chapter.page_count,
                    blocks=[b.model_dump(exclude_none=True) for b in chapter.blocks],
                )
            )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="product",
                entity_id=product_id,
                action="product.chapters_replaced",
                payload={"count": len(payload.chapters)},
            )
        )
    return {"count": len(payload.chapters)}
