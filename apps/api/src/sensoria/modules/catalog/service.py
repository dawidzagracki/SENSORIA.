"""Catalog creation, durable slugs, and the single publication validation path."""

import re
from collections.abc import Iterable
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.shared.audit_log import ActorType
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate

from .inventory import append_stock_movement
from .models import (
    Category,
    Product,
    ProductAudiobook,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
)
from .slug import SLUG_MAX_LENGTH, slugify
from .types import ProductKind, ProductStatus

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _product_details(
    product: Product,
) -> tuple[object | None, object | None, object | None, object | None]:
    state = inspect(product)
    names = ("voucher", "book", "audiobook", "digital")
    values: list[object | None] = []
    for name in names:
        if name not in state.dict and not state.transient:
            raise DomainError(
                "PRODUCT_DETAILS_NOT_LOADED",
                "Nie można zweryfikować produktu bez jawnie załadowanych szczegółów.",
                409,
            )
        value = state.dict.get(name)
        values.append(value)
    return cast(tuple[object | None, object | None, object | None, object | None], tuple(values))


def validate_product_for_publication(product: Product) -> None:
    """Check the complete publication contract without changing product state."""

    if not product.name or not product.name.strip():
        raise DomainError("PRODUCT_NAME_REQUIRED", "Nazwa produktu jest wymagana.")
    if (
        not product.slug
        or len(product.slug) > SLUG_MAX_LENGTH
        or _SLUG_PATTERN.fullmatch(product.slug) is None
    ):
        raise DomainError("PRODUCT_SLUG_INVALID", "Slug produktu jest nieprawidłowy.")
    if product.price is None or product.price < 0:
        raise DomainError(
            "PRODUCT_PRICE_REQUIRED", "Cena produktu jest wymagana i nie może być ujemna."
        )
    if not isinstance(product.vat_rate, VatRate):
        raise DomainError("PRODUCT_VAT_REQUIRED", "Stawka VAT produktu jest wymagana.")

    state = inspect(product)
    if "images" not in state.dict and not state.transient:
        raise DomainError(
            "PRODUCT_IMAGES_NOT_LOADED",
            "Nie można zweryfikować produktu bez jawnie załadowanej galerii.",
            409,
        )
    images = cast(Iterable[ProductImage], state.dict.get("images", ()))
    if not any(image.url.strip() and image.alt.strip() for image in images):
        raise DomainError(
            "PRODUCT_IMAGE_REQUIRED", "Opublikowany produkt musi mieć co najmniej jeden obraz."
        )

    voucher, book, audiobook, digital = _product_details(product)
    expected: dict[ProductKind, object | None] = {
        ProductKind.VOUCHER: voucher,
        ProductKind.BOOK: book,
        ProductKind.AUDIOBOOK: audiobook,
        ProductKind.DIGITAL: digital,
    }
    if expected[product.kind] is None or sum(value is not None for value in expected.values()) != 1:
        raise DomainError(
            "PRODUCT_DETAILS_REQUIRED",
            "Produkt musi mieć dokładnie jeden zestaw szczegółów zgodny z jego rodzajem.",
        )

    if product.kind is ProductKind.VOUCHER:
        voucher_details = cast(ProductVoucher, voucher)
        if not voucher_details.service_name.strip() or not voucher_details.variants:
            raise DomainError(
                "PRODUCT_VOUCHER_DETAILS_REQUIRED",
                "Voucher musi określać usługę i co najmniej jeden wariant.",
            )
        if any(variant.price < 0 for variant in voucher_details.variants):
            raise DomainError("PRODUCT_VARIANT_PRICE_INVALID", "Cena wariantu nie może być ujemna.")
    elif product.kind is ProductKind.BOOK:
        book_details = cast(ProductBook, book)
        if book_details.stock_quantity < 0 or (book_details.low_stock_threshold or 0) < 0:
            raise DomainError(
                "PRODUCT_BOOK_STOCK_INVALID", "Stan i próg magazynowy nie mogą być ujemne."
            )
        if book_details.weight_grams is not None and book_details.weight_grams <= 0:
            raise DomainError("PRODUCT_BOOK_WEIGHT_INVALID", "Waga książki musi być dodatnia.")
        dimensions = (
            book_details.length_mm,
            book_details.width_mm,
            book_details.height_mm,
        )
        if any(value is not None for value in dimensions) and any(
            value is None or value <= 0 for value in dimensions
        ):
            raise DomainError(
                "PRODUCT_BOOK_DIMENSIONS_INVALID",
                "Podaj wszystkie dodatnie wymiary książki albo pozostaw je puste.",
            )
    elif product.kind is ProductKind.AUDIOBOOK:
        audiobook_details = cast(ProductAudiobook, audiobook)
        if (
            audiobook_details.duration_seconds is None
            or audiobook_details.duration_seconds <= 0
            or not audiobook_details.narrator
            or not audiobook_details.narrator.strip()
            or not audiobook_details.chapters
        ):
            raise DomainError(
                "PRODUCT_AUDIOBOOK_DETAILS_REQUIRED",
                "Audiobook musi określać czas trwania, lektora i co najmniej jeden rozdział.",
            )
        chapter_total = sum(chapter.length_seconds for chapter in audiobook_details.chapters)
        if chapter_total != audiobook_details.duration_seconds:
            raise DomainError(
                "AUDIOBOOK_DURATION_MISMATCH",
                "Suma czasów rozdziałów musi być równa całkowitemu czasowi audiobooka.",
            )
    else:
        digital_details = cast(ProductDigital, digital)
        if not digital_details.file_format.strip():
            raise DomainError(
                "PRODUCT_DIGITAL_DETAILS_REQUIRED", "Format pliku produktu cyfrowego jest wymagany."
            )


async def publish_product(session: AsyncSession, product: Product) -> Product:
    """Publish one draft atomically; timestamp comes from PostgreSQL transaction time."""

    if product.status is ProductStatus.PUBLISHED:
        return product
    if product.status is ProductStatus.WITHDRAWN:
        raise DomainError("PRODUCT_WITHDRAWN", "Wycofanego produktu nie można opublikować.", 409)
    if not product.slug:
        product.slug = slugify(product.name) or "product"
    validate_product_for_publication(product)

    async with session.begin_nested():
        session.add(product)
        product.status = ProductStatus.PUBLISHED
        needs_timestamp = product.published_at is None
        if needs_timestamp:
            product.published_at = cast(datetime, func.now())
        await session.flush()
        if needs_timestamp:
            await session.refresh(product, attribute_names=["published_at"])
    return product


async def create_and_publish_product(session: AsyncSession, product: Product) -> Product:
    """Create and publish a complete product, retrying database slug collisions."""

    base_slug = product.slug or slugify(product.name) or "product"
    if _SLUG_PATTERN.fullmatch(base_slug) is None or len(base_slug) > SLUG_MAX_LENGTH:
        raise DomainError("PRODUCT_SLUG_INVALID", "Slug produktu jest nieprawidłowy.")
    opening_stock = 0
    if product.kind is ProductKind.BOOK and product.book is not None:
        opening_stock = product.book.stock_quantity
        product.book.stock_quantity = 0
    for attempt in range(1, 1000):
        suffix = "" if attempt == 1 else f"-{attempt}"
        candidate = f"{base_slug[: SLUG_MAX_LENGTH - len(suffix)].rstrip('-')}{suffix}"
        product.slug = candidate
        try:
            published = await publish_product(session, product)
            if opening_stock:
                await append_stock_movement(
                    session,
                    product_id=published.id,
                    change=opening_stock,
                    reason="correction",
                    operation_key=f"opening:{published.id}",
                    actor_id=None,
                    actor_type=ActorType.SYSTEM,
                    note="Stan otwarcia zapisany przy utworzeniu produktu.",
                )
            return published
        except IntegrityError as error:
            if _constraint_name(error) != "uq_products_slug":
                raise
            product.status = ProductStatus.DRAFT
            product.published_at = None
    raise DomainError(
        "PRODUCT_SLUG_EXHAUSTED", "Nie udało się nadać unikalnego sluga produktu.", 409
    )


def _constraint_name(error: IntegrityError) -> str | None:
    current: object | None = error.orig
    for _ in range(4):
        direct = getattr(current, "constraint_name", None)
        if isinstance(direct, str):
            return direct
        diagnostic = getattr(current, "diag", None)
        value = getattr(diagnostic, "constraint_name", None)
        if isinstance(value, str):
            return value
        cause = getattr(current, "__cause__", None)
        current = cause if cause is not current else None
        if current is None:
            break
    return None


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    """Expose a read-only lookup for admin tooling without changing slug identity."""

    return bool(await session.scalar(select(Product.id).where(Product.slug == slug).limit(1)))


async def create_category(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    parent_id: UUID | None = None,
    position: int = 0,
) -> Category:
    """Create a category with a durable Polish slug and at most two levels."""

    clean_name = name.strip()
    if not clean_name:
        raise DomainError("CATEGORY_NAME_REQUIRED", "Nazwa kategorii jest wymagana.")
    if position < 0:
        raise DomainError("CATEGORY_POSITION_INVALID", "Pozycja kategorii nie może być ujemna.")
    if parent_id is not None:
        parent = await session.get(Category, parent_id)
        if parent is None:
            raise DomainError(
                "CATEGORY_PARENT_NOT_FOUND", "Nie znaleziono kategorii nadrzędnej.", 404
            )
        if parent.parent_id is not None:
            raise DomainError(
                "CATEGORY_DEPTH_EXCEEDED", "Kategorie mogą mieć najwyżej dwa poziomy."
            )

    base_slug = slugify(clean_name) or "kategoria"
    for attempt in range(1, 1000):
        suffix = "" if attempt == 1 else f"-{attempt}"
        slug = f"{base_slug[: 180 - len(suffix)].rstrip('-')}{suffix}"
        exists = await session.scalar(select(Category.id).where(Category.slug == slug).limit(1))
        if exists is None:
            category = Category(
                name=clean_name,
                slug=slug,
                description=description,
                parent_id=parent_id,
                position=position,
            )
            session.add(category)
            await session.flush()
            return category
    raise DomainError(
        "CATEGORY_SLUG_EXHAUSTED", "Nie udało się nadać unikalnego sluga kategorii.", 409
    )
