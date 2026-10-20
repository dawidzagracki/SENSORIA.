"""Read-only public catalog contracts for product and category pages."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError

from .homepage import DEFAULT_HOMEPAGE_CONTENT, HOMEPAGE_SETTING_KEY, HomepageContent
from .inventory import current_book_inventory
from .models import (
    Category,
    Product,
    ProductAudiobook,
    ProductVoucher,
    SearchQuery,
    product_categories,
)
from .public_catalog import CatalogFilters, get_product_detail, list_products
from .schemas import (
    CatalogListResponse,
    CatalogProductDetail,
    PublicCategory,
    PublicCategoryPage,
    PublicCategoryRef,
    PublicImage,
    PublicOffer,
    PublicProduct,
    PublicSitemap,
    SitemapEntry,
)
from .search import normalize_query
from .search_presentation import (
    DEFAULT_SEARCH_PRESENTATION,
    SEARCH_PRESENTATION_SETTING_KEY,
    SearchPresentationSettings,
)
from .seo import category_meta_description, product_meta_description, product_meta_title
from .types import ProductKind, ProductStatus

router = APIRouter(prefix="/catalog", tags=["catalog"])
products_router = APIRouter(tags=["products"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/public/homepage", response_model=HomepageContent)
async def public_homepage_content(session: SessionDependency) -> HomepageContent:
    """Return only the typed, non-secret homepage settings allowlist."""

    setting = await session.scalar(select(AppSetting).where(AppSetting.key == HOMEPAGE_SETTING_KEY))
    if setting is None:
        return DEFAULT_HOMEPAGE_CONTENT
    try:
        return HomepageContent.model_validate(setting.value)
    except (TypeError, ValueError):
        raise DomainError(
            "HOMEPAGE_SETTINGS_INVALID",
            "Treści strony głównej wymagają poprawnej konfiguracji.",
            500,
        ) from None


@router.get("/public/search-presentation", response_model=SearchPresentationSettings)
async def public_search_presentation(session: SessionDependency) -> SearchPresentationSettings:
    """Return only validated public suggestions and optional contact details."""

    setting = await session.scalar(
        select(AppSetting).where(AppSetting.key == SEARCH_PRESENTATION_SETTING_KEY)
    )
    if setting is None:
        return DEFAULT_SEARCH_PRESENTATION
    try:
        return SearchPresentationSettings.model_validate(setting.value)
    except (TypeError, ValueError):
        raise DomainError(
            "SEARCH_PRESENTATION_SETTINGS_INVALID",
            "Ustawienia strony braku wyników wymagają poprawnej konfiguracji.",
            500,
        ) from None


@products_router.get("/products", response_model=CatalogListResponse)
async def public_product_list(
    session: SessionDependency,
    category: Annotated[
        str | None, Query(max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    ] = None,
    kind: ProductKind | None = None,
    audience: Annotated[
        str | None, Query(max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    ] = None,
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    delivery: Literal["digital", "parcel"] | None = None,
    q: Annotated[str | None, Query(max_length=160)] = None,
    sort: Literal["recommended", "price_asc", "price_desc", "newest", "bestselling"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1)] = 12,
    record_search: bool = True,
) -> CatalogListResponse:
    """List public products with intersecting filters, facets, and page metadata."""

    if per_page > 48:
        raise DomainError("PER_PAGE_OUT_OF_RANGE", "per_page musi mieścić się w zakresie 1–48.")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise DomainError("PRICE_RANGE_INVALID", "price_min nie może być większe niż price_max.")
    if q is not None and any(ord(character) < 32 and not character.isspace() for character in q):
        raise DomainError("SEARCH_QUERY_INVALID", "Parametr q zawiera niedozwolone znaki.")
    normalized_q = " ".join(q.split()) if q and q.strip() else None
    if normalized_q is None and sort is None:
        sort = "recommended"
    filters = CatalogFilters(
        category=category,
        kind=kind,
        audience=audience,
        price_min=price_min,
        price_max=price_max,
        delivery=delivery,
        q=normalized_q,
    )
    response = await list_products(
        session,
        filters=filters,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    if normalized_q is not None and record_search:
        normalized_key = normalize_query(normalized_q)
        if normalized_key is not None:
            session.add(
                SearchQuery(
                    query_text=normalized_q,
                    normalized_query=normalized_key,
                    result_count=response.total,
                )
            )
            # Analytics is part of an explicitly submitted search, including cache hits.
            await session.commit()
    return response


@products_router.get("/products/{slug}", response_model=CatalogProductDetail)
async def public_product_detail(slug: str, session: SessionDependency) -> CatalogProductDetail:
    """Return a public product and a small same-category recommendation set."""

    product = await get_product_detail(session, slug)
    if product is None:
        raise DomainError("PRODUCT_NOT_FOUND", "Nie znaleziono produktu.", 404)
    return product


_PUBLIC_PRODUCT_LOADERS = (
    selectinload(Product.images),
    selectinload(Product.voucher).selectinload(ProductVoucher.variants),
    selectinload(Product.book),
    selectinload(Product.audiobook).selectinload(ProductAudiobook.chapters),
    selectinload(Product.digital),
    selectinload(Product.categories).selectinload(Category.parent),
    selectinload(Product.audience_tags),
)


def _public_product(product: Product, *, is_available: bool | None = None) -> PublicProduct:
    images = product.images
    voucher = product.voucher
    digital = product.digital
    categories = sorted(product.categories, key=lambda item: (item.position, item.slug))
    offers = (
        [PublicOffer(name=variant.kind.value, price=variant.price) for variant in voucher.variants]
        if voucher is not None
        else ([PublicOffer(price=product.price)] if product.price is not None else [])
    )
    published_at = product.published_at
    if published_at is None:
        raise RuntimeError("Opublikowany produkt nie ma czasu publikacji.")
    return PublicProduct(
        id=product.id,
        kind=product.kind,
        digital_label=digital.label if digital is not None else None,
        name=product.name,
        slug=product.slug,
        short_description=product.short_description,
        description=product.description,
        price=product.price,
        compare_at_price=product.compare_at_price,
        vat_rate=product.vat_rate,
        is_available=product.is_available if is_available is None else is_available,
        images=[PublicImage(url=image.url, alt=image.alt) for image in images],
        offers=offers,
        categories=[
            PublicCategoryRef(
                name=category.name,
                slug=category.slug,
                parent_name=category.parent.name if category.parent is not None else None,
                parent_slug=category.parent.slug if category.parent is not None else None,
            )
            for category in categories
        ],
        audience_tags=sorted(tag.name for tag in product.audience_tags),
        meta_title=product_meta_title(product.name, product.meta_title),
        meta_description=product_meta_description(
            product.name,
            product.short_description,
            product.description,
            product.meta_description,
        ),
        og_image=product.og_image or (images[0].url if images else None),
        created_at=product.created_at,
        updated_at=product.updated_at,
        published_at=published_at,
    )


async def _category_count(session: AsyncSession, category_id: UUID) -> int:
    """Count direct published membership only; DISTINCT prevents future join fanout."""

    value = await session.scalar(
        select(func.count(distinct(Product.id)))
        .select_from(product_categories)
        .join(Product, Product.id == product_categories.c.product_id)
        .where(
            product_categories.c.category_id == category_id,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at.is_not(None),
            Product.published_at <= func.now(),
        )
    )
    return int(value or 0)


def _public_category(category: Category, count: int) -> PublicCategory:
    parent = category.parent
    return PublicCategory(
        id=category.id,
        name=category.name,
        slug=category.slug,
        description=category.description,
        parent_slug=parent.slug if parent is not None else None,
        parent_name=parent.name if parent is not None else None,
        position=category.position,
        published_product_count=count,
        meta_title=category.meta_title.strip() if category.meta_title else category.name,
        meta_description=category_meta_description(
            category.name, category.description, category.meta_description
        ),
        # A category image can come from a manual URL or the shared brand setting.
        og_image=category.og_image or get_settings().SITE_OG_IMAGE,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.get("/public/products/{slug}", response_model=PublicProduct)
async def get_public_product(slug: str, session: SessionDependency) -> PublicProduct:
    product = await session.scalar(
        select(Product)
        .where(
            Product.slug == slug,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at.is_not(None),
            Product.published_at <= func.now(),
        )
        .options(*_PUBLIC_PRODUCT_LOADERS)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono produktu.")
    available = product.is_available
    if product.book is not None:
        _, available_quantity = (await current_book_inventory(session, {product.id})).get(
            product.id, (product.book.stock_quantity, 0)
        )
        available = available and available_quantity > 0
    return _public_product(product, is_available=available)


@router.get("/public/categories", response_model=list[PublicCategory])
async def list_public_categories(
    session: SessionDependency,
) -> list[PublicCategory]:
    categories = (
        await session.scalars(
            select(Category)
            .options(selectinload(Category.parent))
            .order_by(Category.position, Category.name)
        )
    ).all()
    return [
        _public_category(category, await _category_count(session, category.id))
        for category in categories
    ]


@router.get("/public/categories/{slug}", response_model=PublicCategoryPage)
async def get_public_category(slug: str, session: SessionDependency) -> PublicCategoryPage:
    category = await session.scalar(
        select(Category).where(Category.slug == slug).options(selectinload(Category.parent))
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono kategorii.")
    products = (
        await session.scalars(
            select(Product)
            .join(product_categories, product_categories.c.product_id == Product.id)
            .where(
                product_categories.c.category_id == category.id,
                Product.status == ProductStatus.PUBLISHED,
                Product.published_at.is_not(None),
                Product.published_at <= func.now(),
            )
            .options(*_PUBLIC_PRODUCT_LOADERS)
            .order_by(Product.sort_order, Product.name)
            .distinct()
        )
    ).all()
    inventory = await current_book_inventory(
        session, {product.id for product in products if product.book is not None}
    )
    return PublicCategoryPage(
        **_public_category(category, len(products)).model_dump(),
        products=[
            _public_product(
                product,
                is_available=(
                    product.is_available and inventory.get(product.id, (0, 0))[1] > 0
                    if product.book is not None
                    else product.is_available
                ),
            )
            for product in products
        ],
    )


@router.get("/public/sitemap", response_model=PublicSitemap)
async def public_sitemap_data(session: SessionDependency) -> PublicSitemap:
    products = (
        await session.scalars(
            select(Product)
            .where(
                Product.status == ProductStatus.PUBLISHED,
                Product.published_at.is_not(None),
                Product.published_at <= func.now(),
            )
            .order_by(Product.slug)
        )
    ).all()
    categories = (await session.scalars(select(Category).order_by(Category.slug))).all()
    return PublicSitemap(
        entries=[
            *[
                SitemapEntry(kind="product", slug=product.slug, last_modified=product.updated_at)
                for product in products
            ],
            *[
                SitemapEntry(kind="category", slug=category.slug, last_modified=category.updated_at)
                for category in categories
            ],
        ]
    )
