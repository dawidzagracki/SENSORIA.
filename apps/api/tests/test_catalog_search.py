"""PostgreSQL integration coverage for Polish full-text product search."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sensoria.database import get_session
from sensoria.main import app
from sensoria.modules.catalog.cache import clear_cache
from sensoria.modules.catalog.models import (
    Category,
    Product,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
    SearchQuery,
)
from sensoria.modules.catalog.search import normalize_query
from sensoria.modules.catalog.service import create_and_publish_product
from sensoria.modules.catalog.types import (
    DigitalLabel,
    ProductKind,
    ProductStatus,
    VoucherVariantKind,
)
from sensoria.shared.types import VatRate
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def catalog_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """Create isolated transaction-scoped PostgreSQL fixture for this test module."""

    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
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
            if transaction.is_active:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client_for_session(catalog_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Bind HTTP requests to the current test's isolated PostgreSQL session."""

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield catalog_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://catalog-search-test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def _new_product(kind: ProductKind, name: str, price: int) -> Product:
    """Create complete test-only domain data without importing another test module."""

    return Product(
        kind=kind,
        name=name,
        slug=f"{kind.value.lower()}-{uuid4().hex}",
        short_description=None,
        description=None,
        price=price,
        compare_at_price=None,
        vat_rate=VatRate.RATE_23,
        images=[ProductImage(url="https://example.invalid/item.webp", alt="Okładka")],
        book=ProductBook(stock_quantity=2) if kind is ProductKind.BOOK else None,
        audiobook=None,
        digital=(
            ProductDigital(file_format="PDF", label=DigitalLabel.EBOOK_PDF)
            if kind is ProductKind.DIGITAL
            else None
        ),
        voucher=(
            ProductVoucher(
                service_name="Konsultacja",
                validity_months=12,
                variants=[ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=price)],
            )
            if kind is ProductKind.VOUCHER
            else None
        ),
        categories=[],
        audience_tags=[],
    )


async def _publish(
    session: AsyncSession,
    kind: ProductKind,
    name: str,
    price: int,
    *,
    categories: list[Category] | None = None,
) -> Product:
    product = _new_product(kind, name, price)
    product.categories = categories or []
    session.add(product)
    return await create_and_publish_product(session, product)


@pytest.fixture(autouse=True)
def reset_search_cache() -> Iterator[None]:
    clear_cache()
    yield
    clear_cache()


@pytest.mark.asyncio
async def test_polish_inflection_accent_folding_and_source_weights(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    named = await _publish(catalog_session, ProductKind.BOOK, "Integracja sensoryczna", 5000)
    accented_book = await _publish(catalog_session, ProductKind.BOOK, "Książka o rozwoju", 5000)
    description = await _publish(catalog_session, ProductKind.DIGITAL, "Poradnik rozwoju", 5000)
    description.description = "Materiały o terapii dzieci oraz integracji sensorycznej."
    await catalog_session.flush()
    title_match = await _publish(catalog_session, ProductKind.DIGITAL, "Terapia sensoryczna", 5000)
    body_match = await _publish(catalog_session, ProductKind.DIGITAL, "Materiały ogólne", 5000)
    body_match.description = "Terapia sensoryczna."
    await catalog_session.flush()

    for query, expected in (
        ("integracja sensoryczna", named.id),
        ("terapii", description.id),
        ("terapia", title_match.id),
    ):
        response = await client_for_session.get("/products", params={"q": query})
        assert response.status_code == 200, response.text
        assert str(expected) in {item["id"] for item in response.json()["items"]}
        if query == "integracja sensoryczna":
            assert str(description.id) in {item["id"] for item in response.json()["items"]}

    accented = await client_for_session.get("/products", params={"q": "książka"})
    unaccented = await client_for_session.get("/products", params={"q": "ksiazka"})
    assert {item["id"] for item in accented.json()["items"]} == {
        item["id"] for item in unaccented.json()["items"]
    }
    assert str(accented_book.id) in {item["id"] for item in accented.json()["items"]}

    ranked = await client_for_session.get("/products", params={"q": "terapia sensoryczna"})
    ranked_ids = [item["id"] for item in ranked.json()["items"]]
    assert ranked_ids.index(str(title_match.id)) < ranked_ids.index(str(body_match.id))


@pytest.mark.asyncio
async def test_search_filters_facets_blank_queries_and_analytics_cache_hits(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category = Category(name="Kursy PDF", slug=f"kursy-{uuid4().hex[:8]}")
    other_category = Category(name="Książki", slug=f"ksiazki-{uuid4().hex[:8]}")
    catalog_session.add_all([category, other_category])
    await catalog_session.flush()
    matching = await _publish(
        catalog_session,
        ProductKind.DIGITAL,
        "Integracja sensoryczna",
        4999,
        categories=[category],
    )
    await _publish(
        catalog_session,
        ProductKind.DIGITAL,
        "Integracja sensoryczna za droga",
        8000,
        categories=[category],
    )
    await _publish(
        catalog_session,
        ProductKind.BOOK,
        "Książka bez integracji",
        4999,
        categories=[other_category],
    )
    hidden_draft = _new_product(ProductKind.DIGITAL, "Integracja sensoryczna szkic", 2000)
    withdrawn = _new_product(ProductKind.DIGITAL, "Integracja sensoryczna wycofana", 2000)
    withdrawn.status = ProductStatus.WITHDRAWN
    withdrawn.published_at = datetime.now(UTC)
    catalog_session.add_all([hidden_draft, withdrawn])
    await catalog_session.flush()

    filtered = await client_for_session.get(
        "/products",
        params={"q": "integracja sensoryczna", "category": category.slug, "price_max": 5000},
    )
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(matching.id)
    kind_counts = {item["value"]: item["count"] for item in body["facets"]["kinds"]}
    assert kind_counts["DIGITAL"] == 1
    assert kind_counts["BOOK"] == 0
    visible_ids = {item["id"] for item in body["items"]}
    assert str(hidden_draft.id) not in visible_ids
    assert str(withdrawn.id) not in visible_ids

    for params in ({}, {"q": ""}, {"q": "   "}):
        ordinary = await client_for_session.get("/products", params=params)
        assert ordinary.json()["total"] == 3
        assert ordinary.json()["suggestions"] is None

    clear_cache()
    await client_for_session.get("/products", params={"q": "integracja sensoryczna"})
    await client_for_session.get("/products", params={"q": "integracja sensoryczna"})
    history = list((await catalog_session.scalars(select(SearchQuery))).all())
    matches = [row for row in history if row.normalized_query == "integracja sensoryczna"]
    assert len(matches) >= 3
    assert all(row.result_count == 2 for row in matches[-2:])
    assert all(row.searched_at is not None for row in matches)
    assert normalize_query(" Książka ") == normalize_query("ksiazka")


@pytest.mark.asyncio
async def test_no_result_suggestions_and_page_out_of_range_are_distinct(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category = Category(name="Vouchery", slug=f"vouchery-{uuid4().hex[:8]}")
    catalog_session.add(category)
    await catalog_session.flush()
    await _publish(
        catalog_session,
        ProductKind.VOUCHER,
        "Konsultacja psychologiczna",
        10000,
        categories=[category],
    )
    related = await _publish(
        catalog_session,
        ProductKind.VOUCHER,
        "Spotkanie z psychologiem",
        12000,
        categories=[category],
    )
    await client_for_session.get("/products", params={"q": "konsultacja"})
    await client_for_session.get("/products", params={"q": "konsultacja"})

    missing = await client_for_session.get("/products", params={"q": "psychologicznaa"})
    body = missing.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["total_pages"] == 0
    assert "konsultacja" in [item.casefold() for item in body["suggestions"]["popular_queries"]]
    assert str(related.id) in {item["id"] for item in body["suggestions"]["related_products"]}

    out_of_range = await client_for_session.get(
        "/products", params={"q": "konsultacja", "page": 99}
    )
    assert out_of_range.json()["total"] == 1
    assert out_of_range.json()["suggestions"] is None


@pytest.mark.asyncio
async def test_database_triggers_refresh_product_and_category_vectors(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category = Category(name="Wsparcie rodzin", slug=f"wsparcie-{uuid4().hex[:8]}")
    product = _new_product(ProductKind.DIGITAL, "Książka o relacjach", 2000)
    product.categories = [category]
    catalog_session.add(product)
    await catalog_session.flush()

    async def matches(term: str) -> bool:
        value = await catalog_session.scalar(
            text(
                "SELECT search_vector @@ plainto_tsquery('public.sensoria_polish', :term) "
                "FROM products WHERE id=:id"
            ),
            {"term": term, "id": product.id},
        )
        return bool(value)

    assert await matches("rodzina")
    product.name = "Przewodnik"
    await catalog_session.flush()
    assert await matches("przewodnik")
    await catalog_session.execute(
        text("UPDATE products SET short_description=:description WHERE id=:id"),
        {"description": "Tekst zapisany poza ORM", "id": product.id},
    )
    assert await matches("zapisany")
    category.name = "Komunikacja"
    await catalog_session.flush()
    assert await matches("komunikacja")
    product.categories.clear()
    await catalog_session.flush()
    assert not await matches("komunikacja")


@pytest.mark.asyncio
async def test_cache_separates_queries_and_rebuilds_after_committed_catalog_change(
    catalog_session: AsyncSession, client_for_session: AsyncClient
) -> None:
    category = Category(name="Poradniki", slug=f"poradniki-{uuid4().hex[:8]}")
    product = await _publish(
        catalog_session,
        ProductKind.DIGITAL,
        "Wsparcie rozwoju",
        5000,
        categories=[category],
    )
    first = await client_for_session.get("/products", params={"q": "rozwoju"})
    different = await client_for_session.get("/products", params={"q": "książka"})
    assert first.json()["total"] == 1
    assert different.json()["total"] == 0

    # Change indexed source through ORM and commit; process cache must be cleared.
    product.name = "Wsparcie emocjonalne"
    await catalog_session.commit()
    old_query = await client_for_session.get("/products", params={"q": "rozwoju"})
    new_query = await client_for_session.get("/products", params={"q": "emocjonalne"})
    assert old_query.json()["total"] == 0
    assert new_query.json()["total"] == 1


@pytest.mark.asyncio
async def test_plain_text_special_input_and_search_indexes(
    client_for_session: AsyncClient, catalog_session: AsyncSession
) -> None:
    response = await client_for_session.get("/products", params={"q": '" OR ! ; --'})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    invalid = await client_for_session.get("/products", params={"q": "bad\u0000query"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "SEARCH_QUERY_INVALID"
    indexes = set(
        (
            await catalog_session.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename='products'")
            )
        ).scalars()
    )
    assert "ix_products_search_vector_gin" in indexes
    assert "ix_products_search_vector_unaccented_gin" in indexes

    await catalog_session.execute(text("SET enable_seqscan = off"))
    plan = "\n".join(
        (
            await catalog_session.execute(
                text(
                    "EXPLAIN SELECT id FROM products WHERE search_vector @@ "
                    "plainto_tsquery('public.sensoria_polish', 'integracja')"
                )
            )
        ).scalars()
    )
    assert "ix_products_search_vector_gin" in plan
