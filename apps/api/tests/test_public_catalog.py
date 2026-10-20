"""Public catalog API integration tests on the isolated PostgreSQL fixture."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sensoria.database import get_session
from sensoria.main import app
from sensoria.modules.catalog.cache import clear_cache, get_cached, set_cached
from sensoria.modules.catalog.homepage import DEFAULT_HOMEPAGE_CONTENT, HOMEPAGE_SETTING_KEY
from sensoria.modules.catalog.models import (
    AudienceTag,
    Category,
    Product,
    ProductAudiobook,
    ProductAudiobookChapter,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
    SearchQuery,
)
from sensoria.modules.catalog.public_catalog import CatalogFilters
from sensoria.modules.catalog.search_presentation import (
    DEFAULT_SEARCH_PRESENTATION,
    SEARCH_PRESENTATION_SETTING_KEY,
)
from sensoria.modules.catalog.service import create_and_publish_product
from sensoria.modules.catalog.types import (
    DigitalLabel,
    ProductKind,
    ProductStatus,
    VoucherVariantKind,
)
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.types import VatRate
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def catalog_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """Use a real PostgreSQL connection and roll the fixture transaction back."""

    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                try:
                    yield session
                finally:
                    await session.rollback()
            if outer_transaction.is_active:
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def clear_catalog_cache() -> Iterator[None]:
    clear_cache()
    yield
    clear_cache()


@pytest_asyncio.fixture
async def client_for_session(catalog_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield catalog_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://catalog-test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def _product(kind: ProductKind, name: str, price: int) -> Product:
    values: dict[str, object] = {
        "kind": kind,
        "name": name,
        "slug": f"{kind.value.lower()}-{uuid4().hex[:10]}",
        "short_description": "Opis demonstracyjny",
        "price": price,
        "vat_rate": VatRate.RATE_23,
        "compare_at_price": None,
        "images": [ProductImage(url="https://example.invalid/item.webp", alt="Obraz produktu")],
        "voucher": None,
        "book": None,
        "audiobook": None,
        "digital": None,
        "categories": [],
        "audience_tags": [],
    }
    if kind is ProductKind.BOOK:
        values["book"] = ProductBook(stock_quantity=3, isbn="978-83-000-0000-0")
    elif kind is ProductKind.AUDIOBOOK:
        values["audiobook"] = ProductAudiobook(
            duration_seconds=120,
            narrator="Lektor",
            chapters=[ProductAudiobookChapter(title="Rozdział", length_seconds=120, position=0)],
        )
    elif kind is ProductKind.DIGITAL:
        values["digital"] = ProductDigital(label=DigitalLabel.EBOOK_PDF, file_format="PDF")
    else:
        values["voucher"] = ProductVoucher(
            service_name="Konsultacja",
            variants=[ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=price)],
        )
    return Product(**values)


async def _publish(
    session: AsyncSession,
    kind: ProductKind,
    name: str,
    price: int,
    *,
    categories: list[Category] | None = None,
    audiences: list[AudienceTag] | None = None,
) -> Product:
    product = _product(kind, name, price)
    session.add(product)
    product.categories = categories or []
    product.audience_tags = audiences or []
    return await create_and_publish_product(session, product)


@pytest.mark.asyncio
async def test_filters_intersect_use_grosz_and_facets_replace_their_own_filter(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    parent = Category(name="Książki", slug="ksiazki")
    child = Category(name="Dla rodziców", slug="dla-rodzicow", parent=parent)
    other = Category(name="Audiobooki", slug="audiobooki")
    audience = AudienceTag(name="Rodzice", slug="rodzice")
    other_audience = AudienceTag(name="Dorośli", slug="dorosli")
    catalog_session.add_all([parent, child, other, audience, other_audience])
    await catalog_session.flush()

    book = await _publish(
        catalog_session,
        ProductKind.BOOK,
        "Książka za pięćdziesiąt",
        5000,
        categories=[child],
        audiences=[audience],
    )
    await _publish(
        catalog_session,
        ProductKind.AUDIOBOOK,
        "Audio za pięćdziesiąt jeden",
        5001,
        categories=[other],
        audiences=[audience, other_audience],
    )
    await _publish(
        catalog_session,
        ProductKind.DIGITAL,
        "PDF za sto pięćdziesiąt",
        15000,
        categories=[parent],
        audiences=[other_audience],
    )

    individual_filters = (
        ({"category": "ksiazki"}, 2),
        ({"kind": "AUDIOBOOK"}, 1),
        ({"audience": "rodzice"}, 2),
        ({"price_min": 5001}, 2),
        ({"price_max": 5000}, 1),
        ({"delivery": "digital"}, 2),
        ({"delivery": "parcel"}, 1),
    )
    for params, expected_total in individual_filters:
        filtered = await client_for_session.get("/products", params=params)
        assert filtered.status_code == 200
        assert filtered.json()["total"] == expected_total

    response = await client_for_session.get(
        "/products",
        params={
            "category": "ksiazki",
            "kind": "BOOK",
            "audience": "rodzice",
            "price_min": 5000,
            "price_max": 5000,
            "delivery": "parcel",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(book.id)
    assert body["items"][0]["price"] == 5000
    assert body["items"][0]["book"]["isbn"] == "978-83-000-0000-0"
    assert body["total_pages"] == 1
    kind_counts = {option["value"]: option["count"] for option in body["facets"]["kinds"]}
    assert kind_counts["BOOK"] == 1
    category_options = {option["value"]: option["count"] for option in body["facets"]["categories"]}
    assert category_options["ksiazki"] == 1
    assert category_options["dla-rodzicow"] == 1
    assert category_options["audiobooki"] == 0
    price_options = {option["value"]: option["count"] for option in body["facets"]["prices"]}
    assert price_options == {"up_to_5000": 1, "5001_to_15000": 0, "over_15000": 0}


@pytest.mark.asyncio
async def test_pagination_validation_empty_page_and_shared_not_found(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    await _publish(catalog_session, ProductKind.DIGITAL, "Jedyny produkt", 4999)
    default = await client_for_session.get("/products")
    assert default.status_code == 200
    assert default.json()["per_page"] == 12
    assert default.json()["total"] == 1

    max_page = await client_for_session.get("/products?per_page=48")
    assert max_page.status_code == 200
    assert max_page.json()["per_page"] == 48
    too_many = await client_for_session.get("/products?per_page=49")
    assert too_many.status_code == 400
    assert too_many.json()["error"]["code"] == "PER_PAGE_OUT_OF_RANGE"
    invalid_range = await client_for_session.get("/products?price_min=500&price_max=499")
    assert invalid_range.status_code == 400
    assert invalid_range.json()["error"]["code"] == "PRICE_RANGE_INVALID"
    invalid_query = await client_for_session.get("/products?price_min=-1")
    assert invalid_query.status_code == 422
    assert set(invalid_query.json()) == {"error"}
    assert (await client_for_session.get("/products?page=0")).status_code == 422
    assert (await client_for_session.get("/products?per_page=0")).status_code == 422
    assert (await client_for_session.get("/products?price_max=-1")).status_code == 422

    beyond = await client_for_session.get("/products?page=9")
    assert beyond.status_code == 200
    assert beyond.json()["items"] == []
    assert beyond.json()["total"] == 1
    assert beyond.json()["facets"]["kinds"]

    missing = await client_for_session.get("/products/no-such-product")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {"code": "PRODUCT_NOT_FOUND", "message": "Nie znaleziono produktu."}
    }


@pytest.mark.asyncio
async def test_details_hide_unpublished_and_return_images_categories_and_related(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category = Category(name="Kursy", slug="kursy")
    catalog_session.add(category)
    await catalog_session.flush()
    first = await _publish(
        catalog_session, ProductKind.DIGITAL, "Produkt szczegółowy", 7900, categories=[category]
    )
    related = await _publish(
        catalog_session, ProductKind.BOOK, "Powiązana książka", 8800, categories=[category]
    )
    active_related = await _publish(
        catalog_session, ProductKind.BOOK, "Dostępna powiązana", 8900, categories=[category]
    )
    draft = _product(ProductKind.DIGITAL, "Szkic prywatny", 9900)
    draft.status = ProductStatus.DRAFT
    catalog_session.add(draft)
    await catalog_session.flush()
    withdrawn = await _publish(catalog_session, ProductKind.DIGITAL, "Wycofany", 9700)
    await catalog_session.execute(
        text("UPDATE products SET status = 'WITHDRAWN' WHERE id = :id"),
        {"id": withdrawn.id},
    )
    await catalog_session.execute(
        text("UPDATE products SET published_at = now() + interval '1 day' WHERE id = :id"),
        {"id": related.id},
    )
    await catalog_session.flush()

    detail = await client_for_session.get(f"/products/{first.slug}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["digital"]["label"] == "EBOOK_PDF"
    assert payload["images"][0]["alt"] == "Obraz produktu"
    assert payload["categories"][0]["slug"] == "kursy"
    assert [item["id"] for item in payload["related_products"]] == [str(active_related.id)]
    listing = await client_for_session.get("/products")
    assert listing.json()["total"] == 2
    assert (await client_for_session.get(f"/products/{draft.slug}")).status_code == 404
    assert (await client_for_session.get(f"/products/{withdrawn.slug}")).status_code == 404
    assert (await client_for_session.get("/products/missing")).status_code == 404


@pytest.mark.asyncio
async def test_sort_modes_are_stable_and_price_limits_are_inclusive(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    low = await _publish(catalog_session, ProductKind.DIGITAL, "Cena 1", 5000)
    mid_a = await _publish(catalog_session, ProductKind.DIGITAL, "Cena 2", 7000)
    mid_b = await _publish(catalog_session, ProductKind.DIGITAL, "Cena 3", 7000)
    high = await _publish(catalog_session, ProductKind.DIGITAL, "Cena 4", 15001)
    for product, seconds_ago in ((low, 4), (mid_a, 2), (mid_b, 2), (high, 1)):
        await catalog_session.execute(
            text(
                "UPDATE products SET published_at = now() - (:seconds * interval '1 second') "
                "WHERE id = :id"
            ),
            {"seconds": seconds_ago, "id": product.id},
        )

    asc = await client_for_session.get("/products?sort=price_asc")
    assert [item["id"] for item in asc.json()["items"]] == [
        str(low.id),
        *[str(product_id) for product_id in sorted((mid_a.id, mid_b.id), key=str)],
        str(high.id),
    ]
    desc = await client_for_session.get("/products?sort=price_desc")
    assert [item["id"] for item in desc.json()["items"]] == [
        str(high.id),
        *[str(product_id) for product_id in sorted((mid_a.id, mid_b.id), key=str)],
        str(low.id),
    ]
    newest = await client_for_session.get("/products?sort=newest")
    assert [item["id"] for item in newest.json()["items"]] == [
        str(high.id),
        *[str(product_id) for product_id in sorted((mid_a.id, mid_b.id), key=str)],
        str(low.id),
    ]
    recommended = await client_for_session.get("/products?sort=recommended")
    assert len(recommended.json()["items"]) == 4
    assert [item["id"] for item in recommended.json()["items"]] == [
        str(high.id),
        *[str(product_id) for product_id in sorted((mid_a.id, mid_b.id), key=str)],
        str(low.id),
    ]
    bestseller = await client_for_session.get("/products?sort=bestselling")
    assert [item["id"] for item in bestseller.json()["items"]] == sorted(
        item["id"] for item in bestseller.json()["items"]
    )
    assert (await client_for_session.get("/products?sort=invalid")).status_code == 422
    assert (await client_for_session.get("/products?kind=INVALID")).status_code == 422
    assert (await client_for_session.get("/products?delivery=express")).status_code == 422
    price_range = await client_for_session.get("/products?price_min=5000&price_max=7000")
    assert price_range.json()["total"] == 3
    price_bands = {
        option["value"]: option["count"]
        for option in (await client_for_session.get("/products")).json()["facets"]["prices"]
    }
    assert price_bands == {"up_to_5000": 1, "5001_to_15000": 2, "over_15000": 1}


@pytest.mark.asyncio
async def test_all_kind_specific_details_are_safe_for_public_cards(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    for index, kind in enumerate(ProductKind):
        await _publish(catalog_session, kind, f"Typ {kind.value}", 1000 + index)

    response = await client_for_session.get("/products?sort=price_asc")
    assert response.status_code == 200
    items = {item["kind"]: item for item in response.json()["items"]}
    assert set(items) == {kind.value for kind in ProductKind}
    assert items["BOOK"]["book"]["isbn"] == "978-83-000-0000-0"
    assert items["AUDIOBOOK"]["audiobook"]["chapters"][0]["title"] == "Rozdział"
    assert items["DIGITAL"]["digital"]["label"] == "EBOOK_PDF"
    assert items["VOUCHER"]["voucher"]["variants"][0]["kind"] == "ONLINE"
    assert all("file_path" not in item and "download_url" not in item for item in items.values())


@pytest.mark.asyncio
async def test_http_cache_reuses_full_response_for_omitted_defaults(
    catalog_session: AsyncSession,
    client_for_session: AsyncClient,
) -> None:
    await _publish(catalog_session, ProductKind.DIGITAL, "Cache test", 1234)
    statements: list[str] = []

    def count_sql(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    bind = catalog_session.get_bind()
    event.listen(bind, "before_cursor_execute", count_sql)
    try:
        first = await client_for_session.get("/products")
        initial_query_count = len(statements)
        statements.clear()
        second = await client_for_session.get("/products?page=1&per_page=12&sort=recommended")
    finally:
        event.remove(bind, "before_cursor_execute", count_sql)

    assert first.json() == second.json()
    assert initial_query_count > 0
    assert statements == []


@pytest.mark.asyncio
async def test_facets_do_not_duplicate_products_or_depend_on_page_or_sort(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category_a = Category(name="A", slug="a")
    category_b = Category(name="B", slug="b")
    audience_a = AudienceTag(name="Rodzice", slug="rodzice")
    audience_b = AudienceTag(name="Dorośli", slug="dorosli")
    catalog_session.add_all([category_a, category_b, audience_a, audience_b])
    await catalog_session.flush()
    await _publish(
        catalog_session,
        ProductKind.DIGITAL,
        "Wielokrotne przypisanie",
        1000,
        categories=[category_a, category_b],
        audiences=[audience_a, audience_b],
    )
    await _publish(
        catalog_session,
        ProductKind.BOOK,
        "Drugi",
        2000,
        categories=[category_a],
        audiences=[audience_a],
    )

    first = await client_for_session.get("/products?page=1&per_page=1&sort=price_asc")
    second = await client_for_session.get("/products?page=2&per_page=1&sort=price_desc")
    assert first.json()["total"] == second.json()["total"] == 2
    assert first.json()["facets"] == second.json()["facets"]
    counts = {item["value"]: item["count"] for item in first.json()["facets"]["categories"]}
    assert counts == {"a": 2, "b": 1}
    audience_counts = {item["value"]: item["count"] for item in first.json()["facets"]["audiences"]}
    assert audience_counts == {"dorosli": 1, "rodzice": 2}


@pytest.mark.asyncio
async def test_cache_key_ttl_commit_invalidation_and_rollback(
    catalog_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sensoria.modules.catalog.cache as catalog_cache

    filters = CatalogFilters(category="a", kind=ProductKind.BOOK, audience="b")
    key = filters.cache_key("recommended", 1, 12)
    set_cached(key, {"items": []})
    assert get_cached(key) == {"items": []}
    assert get_cached(filters.cache_key("recommended", 2, 12)) is None
    assert get_cached(filters.cache_key("price_asc", 1, 12)) is None
    assert get_cached(filters.cache_key("recommended", 1, 24)) is None
    assert (
        get_cached(
            CatalogFilters(category="a", kind=ProductKind.BOOK, audience="other").cache_key(
                "recommended", 1, 12
            )
        )
        is None
    )
    for variant in (
        CatalogFilters(category="a", kind=ProductKind.BOOK, audience="b", price_min=1),
        CatalogFilters(category="a", kind=ProductKind.BOOK, audience="b", price_max=1),
        CatalogFilters(category="a", kind=ProductKind.BOOK, audience="b", delivery="digital"),
        CatalogFilters(category="a", kind=ProductKind.AUDIOBOOK, audience="b"),
    ):
        assert get_cached(variant.cache_key("recommended", 1, 12)) is None
    assert (
        get_cached(
            CatalogFilters(category="b", kind=ProductKind.BOOK, audience="b").cache_key(
                "recommended", 1, 12
            )
        )
        is None
    )

    now = [10.0]
    monkeypatch.setattr(catalog_cache, "_now", lambda: now[0])
    set_cached(("ttl",), "cached")
    now[0] += 31
    assert get_cached(("ttl",)) is None

    set_cached(("rollback",), "preserved")
    catalog_session.add(_product(ProductKind.DIGITAL, "Wycofane w rollbacku", 100))
    await catalog_session.flush()
    await catalog_session.rollback()
    assert get_cached(("rollback",)) == "preserved"

    set_cached(("commit",), "stale")
    product = await create_and_publish_product(
        catalog_session, _product(ProductKind.DIGITAL, "Zmiana po commit", 200)
    )
    assert product.id is not None
    await catalog_session.commit()
    assert get_cached(("commit",)) is None
    set_cached(("price-update",), "stale")
    product.price = 201
    await catalog_session.commit()
    assert get_cached(("price-update",)) is None
    set_cached(("category-commit",), "stale")
    catalog_session.add(Category(name="Nowa kategoria", slug=f"nowa-{uuid4().hex[:8]}"))
    await catalog_session.commit()
    assert get_cached(("category-commit",)) is None


@pytest.mark.asyncio
async def test_list_query_count_is_constant_for_1_12_48_and_facets_use_one_union(
    catalog_session: AsyncSession,
    client_for_session: AsyncClient,
) -> None:
    for index in range(48):
        await _publish(
            catalog_session,
            ProductKind.DIGITAL,
            f"Produkt stałego SQL {index:02d}",
            1000 + index,
        )

    async def query_count(per_page: int) -> tuple[int, list[str]]:
        statements: list[str] = []

        def count_sql(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        bind = catalog_session.get_bind()
        event.listen(bind, "before_cursor_execute", count_sql)
        try:
            clear_cache()
            response = await client_for_session.get(
                "/products", params={"per_page": per_page, "sort": "price_asc"}
            )
            assert response.status_code == 200
            assert len(response.json()["items"]) == per_page
        finally:
            event.remove(bind, "before_cursor_execute", count_sql)
        return len(statements), statements

    counts = [await query_count(size) for size in (1, 12, 48)]
    assert counts[0][0] == counts[1][0] == counts[2][0]
    assert sum("UNION ALL" in statement.upper() for statement in counts[0][1]) == 1
    print(f"catalog SQL queries (per_page 1/12/48): {[item[0] for item in counts]}")


@pytest.mark.asyncio
async def test_empty_catalog_has_zero_pages_and_public_scheduled_products_are_hidden(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    empty = await client_for_session.get("/products")
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 0
    assert empty.json()["total_pages"] == 0

    scheduled = await create_and_publish_product(
        catalog_session, _product(ProductKind.DIGITAL, "Zaplanowany", 1234)
    )
    await catalog_session.execute(
        text("UPDATE products SET published_at = now() + interval '1 day' WHERE id = :id"),
        {"id": scheduled.id},
    )
    await catalog_session.flush()
    clear_cache()
    body = (await client_for_session.get("/products")).json()
    assert body["total"] == 0
    assert body["items"] == []
    assert all(option["count"] == 0 for option in body["facets"]["kinds"])
    assert (await client_for_session.get(f"/products/{scheduled.slug}")).status_code == 404


@pytest.mark.asyncio
async def test_homepage_settings_endpoint_exposes_only_typed_public_content(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    initial = await client_for_session.get("/catalog/public/homepage")
    assert initial.status_code == 200
    assert initial.json()["headline"] == {
        "before_emphasis": "Terapia",
        "emphasis": "nie kończy się",
        "after_emphasis": "w gabinecie.",
    }
    assert len(initial.json()["benefits"]) == 4

    changed = DEFAULT_HOMEPAGE_CONTENT.model_dump(mode="json")
    changed["eyebrow"] = "Zmieniona treść z ustawień"
    catalog_session.add(AppSetting(key=HOMEPAGE_SETTING_KEY, value=changed, description="test"))
    catalog_session.add(
        AppSetting(key="private.test-secret", value={"secret": "never-public"}, description="test")
    )
    await catalog_session.flush()

    response = await client_for_session.get("/catalog/public/homepage")
    assert response.status_code == 200
    assert response.json()["eyebrow"] == "Zmieniona treść z ustawień"
    assert "private.test-secret" not in response.text
    assert "never-public" not in response.text


@pytest.mark.asyncio
async def test_search_presentation_is_allowlisted_and_validated(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    initial = await client_for_session.get("/catalog/public/search-presentation")
    assert initial.status_code == 200
    assert initial.json()["suggested_queries"] == DEFAULT_SEARCH_PRESENTATION.suggested_queries
    assert initial.json()["contact_email"] is None
    assert "secret" not in initial.text

    configured = {
        "suggested_queries": ["integracja sensoryczna", "terapia ręki"],
        "contact_email": "kontakt@example.invalid",
        "contact_phone": "+48 111 222 333",
    }
    catalog_session.add(
        AppSetting(
            key=SEARCH_PRESENTATION_SETTING_KEY,
            value=configured,
            description="Ustawienia publiczne testowe",
        )
    )
    await catalog_session.flush()
    response = await client_for_session.get("/catalog/public/search-presentation")
    assert response.status_code == 200
    assert response.json() == configured

    setting = await catalog_session.scalar(
        select(AppSetting).where(AppSetting.key == SEARCH_PRESENTATION_SETTING_KEY)
    )
    assert setting is not None
    setting.value = {
        "suggested_queries": ["integracja sensoryczna"],
        "contact_email": "javascript:alert(1)",
        "contact_phone": None,
        "private_secret": "do-not-return",
    }
    await catalog_session.flush()
    invalid = await client_for_session.get("/catalog/public/search-presentation")
    assert invalid.status_code == 500
    assert "do-not-return" not in invalid.text
    assert "javascript:" not in invalid.text


@pytest.mark.asyncio
async def test_auxiliary_catalog_query_can_skip_search_analytics(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    await _publish(catalog_session, ProductKind.DIGITAL, "Terapia sensoryczna", 5000)
    clear_cache()
    response = await client_for_session.get("/products?q=terapia&record_search=false")
    assert response.status_code == 200
    count = await catalog_session.scalar(select(func.count()).select_from(SearchQuery))
    assert count == 0
