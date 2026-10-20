"""Public product-list and detail queries, facets, ordering, and response mapping."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from math import ceil
from typing import Any, Literal, cast

from sqlalchemy import and_, distinct, func, literal, literal_column, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from sqlalchemy.sql.elements import ColumnElement

from sensoria.config import get_settings

from .cache import get_cached, set_cached
from .inventory import current_book_inventory
from .models import (
    AudienceTag,
    Category,
    Product,
    ProductAudiobook,
    ProductVoucher,
)
from .price_history import lowest_price_before_current_discount
from .sample_storage import LocalSampleStorage
from .schemas import (
    CatalogAudiobookChapter,
    CatalogAudiobookDetails,
    CatalogBookDetails,
    CatalogBookProductDetails,
    CatalogDigitalDetails,
    CatalogFacetOption,
    CatalogFacets,
    CatalogListItem,
    CatalogListResponse,
    CatalogProductDetail,
    CatalogSearchSuggestions,
    CatalogVoucherDetails,
    CatalogVoucherVariant,
    PublicCategoryRef,
    PublicImage,
)
from .search import canonical_query, normalize_query, search_predicate, search_rank
from .seo import product_meta_description, product_meta_title
from .types import ProductKind, ProductStatus

Delivery = Literal["digital", "parcel"]
SortMode = Literal["recommended", "price_asc", "price_desc", "newest", "bestselling"]

_LOADERS = (
    selectinload(Product.images),
    selectinload(Product.book),
    selectinload(Product.audiobook).selectinload(ProductAudiobook.chapters),
    selectinload(Product.digital),
    selectinload(Product.voucher).selectinload(ProductVoucher.variants),
    selectinload(Product.categories).selectinload(Category.parent),
    selectinload(Product.audience_tags),
)
_PRICE_BANDS: tuple[tuple[str, str, int | None, int | None], ...] = (
    ("up_to_5000", "Do 50 zł", 0, 5000),
    ("5001_to_15000", "Powyżej 50 do 150 zł", 5001, 15000),
    ("over_15000", "Powyżej 150 zł", 15001, None),
)
_KIND_LABELS = {
    ProductKind.VOUCHER: "Voucher",
    ProductKind.BOOK: "Książka papierowa",
    ProductKind.AUDIOBOOK: "Audiobook",
    ProductKind.DIGITAL: "Produkt cyfrowy",
}
_DELIVERY_LABELS = {"digital": "Dostawa cyfrowa", "parcel": "Przesyłka"}


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    category: str | None = None
    kind: ProductKind | None = None
    audience: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    delivery: Delivery | None = None
    q: str | None = None

    def cache_key(self, sort: SortMode | None, page: int, per_page: int) -> tuple[object, ...]:
        """Include every normalized filtering and paging input in cache identity."""

        return (
            self.category,
            self.kind.value if self.kind else None,
            self.audience,
            self.price_min,
            self.price_max,
            self.delivery,
            canonical_query(self.q),
            sort,
            page,
            per_page,
        )


def _category_clause(slug: str) -> ColumnElement[bool]:
    """Match a category and its direct children (the taxonomy has max depth two)."""

    return Product.categories.any(
        or_(Category.slug == slug, Category.parent.has(Category.slug == slug))
    )


def _price_band_clause(low: int, high: int | None) -> ColumnElement[bool]:
    conditions = [Product.price >= low]
    if high is not None:
        conditions.append(Product.price <= high)
    return and_(*conditions)


def _conditions(
    filters: CatalogFilters,
    omitted: frozenset[str] = frozenset(),
) -> list[ColumnElement[bool]]:
    conditions = [
        Product.status == ProductStatus.PUBLISHED,
        Product.published_at.is_not(None),
        Product.published_at <= func.now(),
        Product.price.is_not(None),
    ]
    if filters.category is not None and "category" not in omitted:
        conditions.append(_category_clause(filters.category))
    if filters.kind is not None and "kind" not in omitted:
        conditions.append(Product.kind == filters.kind)
    if filters.audience is not None and "audience" not in omitted:
        conditions.append(Product.audience_tags.any(AudienceTag.slug == filters.audience))
    if filters.delivery is not None and "delivery" not in omitted:
        if filters.delivery == "digital":
            conditions.append(Product.kind.in_((ProductKind.DIGITAL, ProductKind.AUDIOBOOK)))
        else:
            conditions.append(Product.kind == ProductKind.BOOK)
    if filters.price_min is not None and "price" not in omitted:
        conditions.append(Product.price >= filters.price_min)
    if filters.price_max is not None and "price" not in omitted:
        conditions.append(Product.price <= filters.price_max)
    normalized_query = " ".join(filters.q.split()) if filters.q and filters.q.strip() else None
    if normalized_query is not None:
        conditions.append(search_predicate(normalized_query))
    return conditions


async def _facet_counts(session: AsyncSession, filters: CatalogFilters) -> CatalogFacets:
    """Return all available option counts in one SQL statement, without join fanout."""

    rows = []
    category_option = aliased(Category)
    category_count = (
        select(func.count(distinct(Product.id)))
        .where(
            *_conditions(filters, frozenset({"category"})),
            Product.categories.any(
                or_(
                    Category.id == category_option.id,
                    Category.parent_id == category_option.id,
                )
            ),
        )
        .correlate(category_option)
        .scalar_subquery()
    )
    rows.append(
        select(
            literal("categories").label("facet"),
            category_option.slug.label("value"),
            category_option.name.label("label"),
            category_count.label("count"),
        )
    )

    audience_option = aliased(AudienceTag)
    audience_count = (
        select(func.count(distinct(Product.id)))
        .where(
            *_conditions(filters, frozenset({"audience"})),
            Product.audience_tags.any(AudienceTag.id == audience_option.id),
        )
        .correlate(audience_option)
        .scalar_subquery()
    )
    rows.append(
        select(
            literal("audiences").label("facet"),
            audience_option.slug.label("value"),
            audience_option.name.label("label"),
            audience_count.label("count"),
        )
    )

    for kind in ProductKind:
        count = (
            select(func.count(distinct(Product.id)))
            .where(*_conditions(filters, frozenset({"kind"})), Product.kind == kind)
            .scalar_subquery()
        )
        rows.append(
            select(
                literal("kinds").label("facet"),
                literal(kind.value).label("value"),
                literal(_KIND_LABELS[kind]).label("label"),
                count.label("count"),
            )
        )

    for delivery, label in _DELIVERY_LABELS.items():
        delivery_condition = (
            Product.kind.in_((ProductKind.DIGITAL, ProductKind.AUDIOBOOK))
            if delivery == "digital"
            else Product.kind == ProductKind.BOOK
        )
        count = (
            select(func.count(distinct(Product.id)))
            .where(
                *_conditions(filters, frozenset({"delivery"})),
                delivery_condition,
            )
            .scalar_subquery()
        )
        rows.append(
            select(
                literal("deliveries").label("facet"),
                literal(delivery).label("value"),
                literal(label).label("label"),
                count.label("count"),
            )
        )

    for value, label, low, high in _PRICE_BANDS:
        band = _price_band_clause(low or 0, high)
        count = (
            select(func.count(distinct(Product.id)))
            .where(*_conditions(filters, frozenset({"price"})), band)
            .scalar_subquery()
        )
        rows.append(
            select(
                literal("prices").label("facet"),
                literal(value).label("value"),
                literal(label).label("label"),
                count.label("count"),
            )
        )

    facet_rows = union_all(*rows).subquery()
    result = await session.execute(
        select(facet_rows.c.facet, facet_rows.c.value, facet_rows.c.label, facet_rows.c.count)
        .select_from(facet_rows)
        .order_by(facet_rows.c.facet, facet_rows.c.label, facet_rows.c.value)
    )
    options: dict[str, list[CatalogFacetOption]] = {
        "categories": [],
        "kinds": [],
        "audiences": [],
        "deliveries": [],
        "prices": [],
    }
    for facet, value, label, count in result:
        options[str(facet)].append(
            CatalogFacetOption(value=str(value), label=str(label), count=int(count or 0))
        )
    return CatalogFacets(**options)


def _list_item(product: Product) -> CatalogListItem:
    image = product.images[0] if product.images else None
    book = product.book
    audiobook = product.audiobook
    digital = product.digital
    voucher = product.voucher
    return CatalogListItem(
        id=product.id,
        slug=product.slug,
        name=product.name,
        kind=product.kind,
        vat_rate=product.vat_rate,
        is_available=product.is_available,
        digital_label=digital.label if digital is not None else None,
        short_description=product.short_description,
        price=cast(int, product.price),
        compare_at_price=product.compare_at_price,
        image=PublicImage(url=image.url, alt=image.alt) if image is not None else None,
        book=(
            CatalogBookDetails(
                stock_quantity=book.stock_quantity,
                available_quantity=book.stock_quantity,
                weight_grams=book.weight_grams,
                length_mm=book.length_mm,
                width_mm=book.width_mm,
                height_mm=book.height_mm,
                isbn=book.isbn,
                binding=book.binding,
                shipping_business_days=book.shipping_business_days,
                shipping_method=book.shipping_method,
            )
            if book is not None
            else None
        ),
        audiobook=(
            CatalogAudiobookDetails(
                duration_seconds=audiobook.duration_seconds,
                narrator=audiobook.narrator,
                chapters=[
                    CatalogAudiobookChapter(
                        title=chapter.title,
                        length_seconds=chapter.length_seconds,
                        position=chapter.position,
                    )
                    for chapter in audiobook.chapters
                ],
                file_format=audiobook.file_format,
            )
            if audiobook is not None
            else None
        ),
        digital=(
            CatalogDigitalDetails(
                page_count=digital.page_count,
                file_format=digital.file_format,
                edition=digital.edition,
                label=digital.label,
            )
            if digital is not None
            else None
        ),
        voucher=(
            CatalogVoucherDetails(
                validity_months=voucher.validity_months,
                service_name=voucher.service_name,
                variants=[
                    CatalogVoucherVariant(id=variant.id, kind=variant.kind, price=variant.price)
                    for variant in voucher.variants
                ],
            )
            if voucher is not None
            else None
        ),
    )


def _ordering(sort: SortMode) -> tuple[ColumnElement[Any], ...]:
    """Map validated sort keys to fixed SQL expressions, always ending in id."""

    orders: dict[str, tuple[ColumnElement[Any], ...]] = {
        "recommended": (Product.sort_order.asc(), Product.published_at.desc()),
        "price_asc": (Product.price.asc(),),
        "price_desc": (Product.price.desc(),),
        "newest": (Product.published_at.desc(),),
        # No order/sales model exists yet. All measured sales are therefore zero.
        "bestselling": (),
    }
    return (*orders[sort], Product.id.asc())


async def list_products(
    session: AsyncSession,
    *,
    filters: CatalogFilters,
    sort: SortMode | None,
    page: int,
    per_page: int,
) -> CatalogListResponse:
    """Read one paged catalog response with unique products and cached facets."""

    cache_key = filters.cache_key(sort, page, per_page)
    cached = get_cached(cache_key)
    if isinstance(cached, CatalogListResponse):
        return await _apply_live_inventory(session, cached)

    total_value = await session.scalar(
        select(func.count(distinct(Product.id))).where(*_conditions(filters))
    )
    total = int(total_value or 0)
    facets = await _facet_counts(session, filters)
    active_query = " ".join(filters.q.split()) if filters.q and filters.q.strip() else None
    effective_sort = sort or ("recommended" if active_query is None else "relevance")
    ordering = (
        (search_rank(active_query).desc(), Product.published_at.desc(), Product.id.asc())
        if effective_sort == "relevance" and active_query is not None
        else _ordering(cast(SortMode, effective_sort))
    )
    page_query = (
        select(Product)
        .where(*_conditions(filters))
        .options(*_LOADERS)
        .order_by(*ordering)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    products = (await session.scalars(page_query)).all()
    suggestions = None
    if total == 0 and active_query is not None:
        suggestions = await _search_suggestions(session, filters, active_query)
    response = CatalogListResponse(
        items=[_list_item(product) for product in products],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=ceil(total / per_page) if total else 0,
        facets=facets,
        suggestions=suggestions,
    )
    set_cached(cache_key, response)
    return await _apply_live_inventory(session, response)


async def _apply_live_inventory(
    session: AsyncSession, response: CatalogListResponse
) -> CatalogListResponse:
    """Keep stock availability out of the process cache because holds change per checkout."""

    items = list(response.items)
    suggestions = response.suggestions
    if suggestions is not None:
        items.extend(suggestions.related_products)
    states = await current_book_inventory(
        session, {item.id for item in items if item.kind is ProductKind.BOOK}
    )

    omnibus: dict[Any, tuple[int | None, datetime | None]] = {}
    for item in items:
        if item.compare_at_price is not None and item.compare_at_price > item.price:
            omnibus[item.id] = await lowest_price_before_current_discount(
                session, item.id, price=item.price, compare_at_price=item.compare_at_price
            )

    def update_item(item: CatalogListItem) -> CatalogListItem:
        if item.id in omnibus:
            lowest, started = omnibus[item.id]
            item = item.model_copy(
                update={"lowest_price_before_discount": lowest, "discount_started_at": started}
            )
        if item.kind is not ProductKind.BOOK or item.book is None:
            return item
        physical, available = states.get(item.id, (item.book.stock_quantity, 0))
        return item.model_copy(
            update={
                "is_available": item.is_available and available > 0,
                "book": item.book.model_copy(
                    update={"stock_quantity": physical, "available_quantity": available}
                ),
            }
        )

    updated_items = [update_item(item) for item in response.items]
    updated_suggestions = (
        suggestions.model_copy(
            update={
                "related_products": [update_item(item) for item in suggestions.related_products]
            }
        )
        if suggestions is not None
        else None
    )
    return response.model_copy(update={"items": updated_items, "suggestions": updated_suggestions})


async def _search_suggestions(
    session: AsyncSession, filters: CatalogFilters, query: str
) -> CatalogSearchSuggestions:
    """Suggest real popular terms and same-category products from nearest public title."""

    from .models import SearchQuery

    normalized_query = normalize_query(query)
    popular_rows = await session.execute(
        select(
            func.max(SearchQuery.query_text),
            func.count(SearchQuery.id).label("usage_count"),
        )
        .where(SearchQuery.normalized_query != (normalized_query or ""))
        .group_by(SearchQuery.normalized_query)
        .order_by(func.count(SearchQuery.id).desc(), SearchQuery.normalized_query.asc())
        .limit(5)
    )
    popular_queries = [str(row[0]) for row in popular_rows if row[0]]

    unsearched_filters = replace(filters, q=None)
    unaccent_dictionary: ColumnElement[Any] = literal_column("'public.unaccent'::regdictionary")
    normalized_text = func.unaccent(unaccent_dictionary, func.lower(query))
    similarity = func.similarity(
        func.unaccent(unaccent_dictionary, func.lower(Product.name)),
        normalized_text,
    )
    nearest_id = await session.scalar(
        select(Product.id)
        .where(*_conditions(unsearched_filters))
        .where(similarity >= 0.05)
        .order_by(similarity.desc(), Product.id.asc())
        .limit(1)
    )
    if nearest_id is None:
        return CatalogSearchSuggestions(popular_queries=popular_queries, related_products=[])

    # Use the explicit association table to anchor suggestions to the nearest product.
    from .models import product_categories

    nearest_categories = select(product_categories.c.category_id).where(
        product_categories.c.product_id == nearest_id
    )
    related = list(
        (
            await session.scalars(
                select(Product)
                .where(
                    Product.id != nearest_id,
                    *_conditions(unsearched_filters),
                    Product.categories.any(Category.id.in_(nearest_categories)),
                )
                .options(*_LOADERS)
                .order_by(Product.sort_order, Product.published_at.desc(), Product.id.asc())
                .limit(4)
            )
        ).all()
    )
    return CatalogSearchSuggestions(
        popular_queries=popular_queries,
        related_products=[_list_item(product) for product in related],
    )


async def get_product_detail(session: AsyncSession, slug: str) -> CatalogProductDetail | None:
    """Load one published product and up to four related products by shared category."""

    product = await session.scalar(
        select(Product)
        .where(
            Product.slug == slug,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at.is_not(None),
            Product.published_at <= func.now(),
            Product.price.is_not(None),
        )
        .options(*_LOADERS)
    )
    if product is None:
        return None

    categories = sorted(product.categories, key=lambda item: (item.position, item.slug))
    category_ids = [category.id for category in categories]
    related: list[Product] = []
    if category_ids:
        related = list(
            (
                await session.scalars(
                    select(Product)
                    .where(
                        Product.id != product.id,
                        Product.status == ProductStatus.PUBLISHED,
                        Product.published_at.is_not(None),
                        Product.published_at <= func.now(),
                        Product.price.is_not(None),
                        Product.categories.any(Category.id.in_(category_ids)),
                    )
                    .options(*_LOADERS)
                    .order_by(Product.sort_order, Product.published_at.desc(), Product.id)
                    .limit(4)
                )
            ).all()
        )

    item = _list_item(product)
    digital = item.digital
    if (
        digital is not None
        and product.price is not None
        and product.compare_at_price is not None
        and product.compare_at_price > product.price
    ):
        lowest_price, discount_started_at = await lowest_price_before_current_discount(
            session,
            product.id,
            price=product.price,
            compare_at_price=product.compare_at_price,
        )
        digital = digital.model_copy(
            update={
                "lowest_price_before_discount": lowest_price,
                "discount_started_at": discount_started_at,
            }
        )
    item_data = item.model_dump()
    item_data["digital"] = digital
    if (
        product.price is not None
        and product.compare_at_price is not None
        and product.compare_at_price > product.price
    ):
        lowest, started = await lowest_price_before_current_discount(
            session, product.id, price=product.price, compare_at_price=product.compare_at_price
        )
        item_data["lowest_price_before_discount"] = lowest
        item_data["discount_started_at"] = started
    sample_storage = LocalSampleStorage(get_settings().SAMPLE_STORAGE_ROOT)
    if product.digital is not None and digital is not None:
        sample_available = product.digital.sample_enabled and sample_storage.exists(
            "pdf", product.digital.sample_file_path
        )
        item_data["digital"] = digital.model_copy(
            update={
                "sample_available": sample_available,
                "sample_pages": product.digital.sample_pages if sample_available else None,
            }
        )
    if product.audiobook is not None and item.audiobook is not None:
        sample_available = product.audiobook.sample_enabled and sample_storage.exists(
            "audio", product.audiobook.sample_file_path
        )
        item_data["audiobook"] = item.audiobook.model_copy(
            update={
                "sample_available": sample_available,
                "sample_duration_seconds": (
                    product.audiobook.sample_duration_seconds if sample_available else None
                ),
            }
        )
    if product.book is not None:
        item_data["book"] = CatalogBookProductDetails(
            weight_grams=product.book.weight_grams,
            length_mm=product.book.length_mm,
            width_mm=product.book.width_mm,
            height_mm=product.book.height_mm,
            isbn=product.book.isbn,
            binding=product.book.binding,
            shipping_business_days=product.book.shipping_business_days,
            shipping_method=product.book.shipping_method,
            stock_quantity=product.book.stock_quantity,
            available_quantity=product.book.stock_quantity,
        ).model_dump()
    response = CatalogProductDetail(
        **item_data,
        description=product.description,
        meta_title=product_meta_title(product.name, product.meta_title),
        meta_description=product_meta_description(
            product.name, product.short_description, product.description, product.meta_description
        ),
        og_image=product.og_image,
        audience_tags=sorted(tag.name for tag in product.audience_tags),
        images=[PublicImage(url=image.url, alt=image.alt) for image in product.images],
        categories=[
            PublicCategoryRef(
                name=category.name,
                slug=category.slug,
                parent_name=category.parent.name if category.parent is not None else None,
                parent_slug=category.parent.slug if category.parent is not None else None,
            )
            for category in categories
        ],
        related_products=[_list_item(candidate) for candidate in related],
        published_at=cast(datetime, product.published_at),
    )
    states = await current_book_inventory(
        session,
        {
            candidate.id
            for candidate in [response, *response.related_products]
            if candidate.kind is ProductKind.BOOK
        },
    )
    if response.kind is ProductKind.BOOK and response.book is not None:
        physical, available = states.get(response.id, (response.book.stock_quantity, 0))
        response = response.model_copy(
            update={
                "is_available": response.is_available and available > 0,
                "book": response.book.model_copy(
                    update={"stock_quantity": physical, "available_quantity": available}
                ),
            }
        )
    related_products = [
        item.model_copy(
            update={
                "is_available": item.is_available and states.get(item.id, (0, 0))[1] > 0,
                "book": item.book.model_copy(
                    update={
                        "stock_quantity": states.get(item.id, (item.book.stock_quantity, 0))[0],
                        "available_quantity": states.get(item.id, (item.book.stock_quantity, 0))[1],
                    }
                ),
            }
        )
        if item.kind is ProductKind.BOOK and item.book is not None
        else item
        for item in response.related_products
    ]
    return response.model_copy(update={"related_products": related_products})
