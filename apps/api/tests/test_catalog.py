"""Catalog model, publication, and seed tests using the isolated PostgreSQL database."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sensoria.database import get_session
from sensoria.main import app
from sensoria.modules.catalog import seed as catalog_seed
from sensoria.modules.catalog.inventory import append_stock_movement
from sensoria.modules.catalog.models import (
    AudienceTag,
    Category,
    LowStockAlert,
    Product,
    ProductAudiobook,
    ProductAudiobookChapter,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
    StockMovement,
    product_categories,
)
from sensoria.modules.catalog.price_history import PriceHistory
from sensoria.modules.catalog.public_catalog import get_product_detail
from sensoria.modules.catalog.schemas import (
    ProductAudiobookChapterInput,
    ProductAudiobookInput,
    ProductDraftInput,
)
from sensoria.modules.catalog.seo import (
    category_meta_description,
    decimal_price,
    plain_description,
    product_meta_description,
    product_meta_title,
)
from sensoria.modules.catalog.service import (
    create_and_publish_product,
    create_category,
    publish_product,
    validate_product_for_publication,
)
from sensoria.modules.catalog.slug import slugify
from sensoria.modules.catalog.types import (
    DigitalLabel,
    ProductKind,
    ProductStatus,
    VoucherVariantKind,
)
from sensoria.shared.audit_log import ActorType
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate
from sqlalchemy import BigInteger, Integer, String, func, insert, inspect, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

API_ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def catalog_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """Use a rollback-isolated connection after applying the real Alembic schema."""

    await asyncio.to_thread(
        command.upgrade,
        Config(str(API_ROOT / "alembic.ini")),
        "head",
    )
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


def _product(
    kind: ProductKind,
    *,
    name: str = "Świadoma seksualność",
    status: ProductStatus = ProductStatus.DRAFT,
) -> Product:
    """Build complete in-memory details for reusable model tests."""

    values: dict[str, object] = {
        "kind": kind,
        "name": name,
        "slug": slugify(name),
        "price": 0,
        "vat_rate": VatRate.RATE_0,
        "status": status,
        "images": [ProductImage(url="https://example.invalid/test.webp", alt="Obraz testowy")],
    }
    if kind is ProductKind.VOUCHER:
        values["voucher"] = ProductVoucher(
            service_name="Usługa testowa",
            variants=[ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=22000)],
        )
    elif kind is ProductKind.BOOK:
        values["book"] = ProductBook(stock_quantity=1)
    elif kind is ProductKind.AUDIOBOOK:
        values["audiobook"] = ProductAudiobook(
            duration_seconds=60,
            narrator="Lektor testowy",
            chapters=[ProductAudiobookChapter(title="Rozdział", length_seconds=60, position=0)],
        )
    else:
        values["digital"] = ProductDigital(file_format="PDF", label=DigitalLabel.EBOOK_PDF)
    return Product(**values)


@pytest.mark.parametrize(
    ("kind", "physical", "digital", "shipping"),
    [
        (ProductKind.VOUCHER, False, False, False),
        (ProductKind.BOOK, True, False, True),
        (ProductKind.AUDIOBOOK, False, True, False),
        (ProductKind.DIGITAL, False, True, False),
    ],
)
def test_product_kind_classification(
    kind: ProductKind, physical: bool, digital: bool, shipping: bool
) -> None:
    product = _product(kind, status=ProductStatus.PUBLISHED)
    assert product.is_physical is physical
    assert product.is_digital is digital
    assert product.requires_shipping is shipping
    assert product.is_available


def test_book_zero_stock_and_unpublished_status_are_unavailable() -> None:
    book = _product(ProductKind.BOOK, status=ProductStatus.PUBLISHED)
    assert book.book is not None
    book.book.stock_quantity = 0
    assert not book.is_available
    assert not _product(ProductKind.DIGITAL).is_available
    assert not _product(ProductKind.DIGITAL, status=ProductStatus.WITHDRAWN).is_available


def test_audiobook_input_rejects_chapter_duration_mismatch() -> None:
    with pytest.raises(ValidationError, match="Suma czasów rozdziałów"):
        ProductAudiobookInput(
            duration_seconds=61,
            chapters=[
                ProductAudiobookChapterInput(title="Rozdział", length_seconds=60, position=0)
            ],
        )


def test_audiobook_input_accepts_exact_chapter_duration_sum() -> None:
    details = ProductAudiobookInput(
        duration_seconds=60,
        chapters=[ProductAudiobookChapterInput(title="Rozdział", length_seconds=60, position=0)],
    )
    assert sum(chapter.length_seconds for chapter in details.chapters) == details.duration_seconds


def test_slugify_handles_polish_separators_empty_and_length() -> None:
    assert slugify("Świadoma seksualność") == "swiadoma-seksualnosc"
    assert slugify("Łódź — książki!!!") == "lodz-ksiazki"
    assert slugify(" -- ") == ""
    assert slugify("A very long title", max_length=8) == "a-very-l"


def test_name_changes_do_not_rewrite_an_existing_slug() -> None:
    product = _product(ProductKind.DIGITAL)
    original = product.slug
    product.name = "Nowa nazwa"
    assert product.slug == original


def test_publication_rejects_missing_image_without_changing_state() -> None:
    product = _product(ProductKind.DIGITAL)
    product.images.clear()
    with pytest.raises(DomainError, match="obraz") as error:
        validate_product_for_publication(product)
    assert error.value.code == "PRODUCT_IMAGE_REQUIRED"
    assert product.status is ProductStatus.DRAFT
    assert product.published_at is None


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("name", "   ", "PRODUCT_NAME_REQUIRED"),
        ("slug", "---", "PRODUCT_SLUG_INVALID"),
        ("price", None, "PRODUCT_PRICE_REQUIRED"),
        ("vat_rate", None, "PRODUCT_VAT_REQUIRED"),
        ("digital", None, "PRODUCT_DETAILS_REQUIRED"),
    ],
)
def test_publication_validation_checks_required_fields(
    field: str, value: object, error_code: str
) -> None:
    product = _product(ProductKind.DIGITAL)
    setattr(product, field, value)
    with pytest.raises(DomainError) as error:
        validate_product_for_publication(product)
    assert error.value.code == error_code
    assert product.status is ProductStatus.DRAFT
    assert product.published_at is None


def test_product_kinds_are_exact_and_digital_labels_are_variants() -> None:
    assert {kind.value for kind in ProductKind} == {"VOUCHER", "BOOK", "AUDIOBOOK", "DIGITAL"}
    assert {label.value for label in DigitalLabel} == {"COURSE_PDF", "EBOOK_PDF"}


def test_draft_schema_keeps_money_integer_and_details_kind_aligned() -> None:
    draft = ProductDraftInput(kind=ProductKind.DIGITAL, price=0)
    assert draft.price == 0
    with pytest.raises(ValidationError):
        ProductDraftInput.model_validate({"kind": ProductKind.DIGITAL, "price": 100.0})
    with pytest.raises(ValidationError):
        ProductDraftInput.model_validate(
            {"kind": ProductKind.BOOK, "digital": {"file_format": "PDF"}}
        )


@pytest.mark.asyncio
async def test_each_kind_persists_with_its_details_and_images(
    catalog_session: AsyncSession,
) -> None:
    for kind in ProductKind:
        product = _product(kind, name=f"Produkt {kind.value} {uuid4().hex[:6]}")
        if product.book is not None:
            product.book.stock_quantity = 0
        catalog_session.add(product)
        await catalog_session.flush()
        loaded = await catalog_session.scalar(
            select(Product)
            .where(Product.id == product.id)
            .options(
                selectinload(Product.images),
                selectinload(Product.voucher).selectinload(ProductVoucher.variants),
                selectinload(Product.book),
                selectinload(Product.audiobook).selectinload(ProductAudiobook.chapters),
                selectinload(Product.digital),
            )
        )
        assert loaded is not None
        assert loaded.kind is kind
        assert len(loaded.images) == 1
        assert (
            sum(
                item is not None
                for item in (loaded.voucher, loaded.book, loaded.audiobook, loaded.digital)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_voucher_default_variants_and_slug_uniqueness(catalog_session: AsyncSession) -> None:
    voucher = ProductVoucher(
        service_name="Konsultacja",
        variants=[
            ProductVoucherVariant(kind=VoucherVariantKind.IN_PERSON, price=25000),
            ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=22000),
        ],
    )
    product = Product(kind=ProductKind.VOUCHER, name="Świadoma seksualność", voucher=voucher)
    product.images.append(ProductImage(url="https://example.invalid/1.webp", alt="Obraz 1"))
    catalog_session.add(product)
    await catalog_session.flush()
    assert voucher.validity_months == 12
    assert product.slug == "swiadoma-seksualnosc"
    assert {variant.price for variant in voucher.variants} == {22000, 25000}

    duplicate = Product(kind=ProductKind.BOOK, name="Inny produkt", slug=product.slug)
    with pytest.raises(IntegrityError):
        async with catalog_session.begin_nested():
            catalog_session.add(duplicate)
            await catalog_session.flush()


@pytest.mark.asyncio
async def test_creation_resolves_a_real_slug_collision(catalog_session: AsyncSession) -> None:
    first = _product(ProductKind.DIGITAL, name="Kolizja nazwy")
    catalog_session.add(first)
    await catalog_session.flush()
    second = _product(ProductKind.DIGITAL, name="Kolizja nazwy")
    created = await create_and_publish_product(catalog_session, second)
    assert first.slug == "kolizja-nazwy"
    assert created.slug == "kolizja-nazwy-2"


@pytest.mark.asyncio
async def test_gallery_and_audiobook_chapters_have_stable_position_order(
    catalog_session: AsyncSession,
) -> None:
    audiobook = ProductAudiobook(
        duration_seconds=90,
        narrator="Lektor",
        chapters=[
            ProductAudiobookChapter(title="Drugi", length_seconds=30, position=1),
            ProductAudiobookChapter(title="Pierwszy", length_seconds=60, position=0),
        ],
    )
    product = Product(
        kind=ProductKind.AUDIOBOOK,
        name="Książka audio",
        audiobook=audiobook,
        images=[
            ProductImage(url="https://example.invalid/2.webp", alt="Drugi", position=1),
            ProductImage(url="https://example.invalid/1.webp", alt="Pierwszy", position=0),
        ],
    )
    catalog_session.add(product)
    await catalog_session.flush()
    loaded = await catalog_session.scalar(
        select(Product)
        .where(Product.id == product.id)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Product.images),
            selectinload(Product.audiobook).selectinload(ProductAudiobook.chapters),
        )
    )
    assert loaded is not None and loaded.audiobook is not None
    assert [image.position for image in loaded.images] == [0, 1]
    assert [chapter.position for chapter in loaded.audiobook.chapters] == [0, 1]


@pytest.mark.asyncio
async def test_one_to_one_details_are_enforced_by_the_database(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.BOOK)
    assert product.book is not None
    product.book.stock_quantity = 0
    catalog_session.add(product)
    await catalog_session.flush()
    with pytest.raises(IntegrityError):
        async with catalog_session.begin_nested():
            await catalog_session.execute(
                insert(ProductBook).values(product_id=product.id, stock_quantity=0)
            )


@pytest.mark.asyncio
async def test_stock_opening_balance_ledger_guard_and_low_stock_alert(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.BOOK, name="Magazyn testowy")
    assert product.book is not None
    product.book.stock_quantity = 3
    product.book.low_stock_threshold = 2
    await create_and_publish_product(catalog_session, product)
    opening = await catalog_session.scalar(
        select(func.sum(StockMovement.change)).where(StockMovement.product_id == product.id)
    )
    assert opening == product.book.stock_quantity == 3

    await append_stock_movement(
        catalog_session,
        product_id=product.id,
        change=-2,
        reason="manual_adjustment",
        operation_key=f"stock-test-crossing:{product.id}",
        actor_id=uuid4(),
        actor_type=ActorType.ADMINISTRATOR,
        note="Kontrolowane zejście poniżej progu.",
    )
    await catalog_session.refresh(product.book)
    assert product.book.stock_quantity == 1
    assert (
        await catalog_session.scalar(
            select(func.count())
            .select_from(LowStockAlert)
            .where(LowStockAlert.product_id == product.id)
        )
        == 1
    )
    with pytest.raises(DBAPIError):
        async with catalog_session.begin_nested():
            await catalog_session.execute(
                update(ProductBook)
                .where(ProductBook.product_id == product.id)
                .values(stock_quantity=9)
            )


@pytest.mark.asyncio
async def test_publish_uses_database_time_and_database_guards(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.DIGITAL)
    published = await create_and_publish_product(catalog_session, product)
    await catalog_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert published.status is ProductStatus.PUBLISHED
    assert published.published_at is not None
    assert published.published_at.tzinfo is not None
    assert published.is_available

    invalid = Product(
        kind=ProductKind.BOOK,
        name="Książka bez szczegółów",
        slug=f"invalid-{uuid4().hex}",
        price=100,
        vat_rate=VatRate.RATE_0,
        status=ProductStatus.PUBLISHED,
    )
    with pytest.raises(IntegrityError):
        async with catalog_session.begin_nested():
            catalog_session.add(invalid)
            await catalog_session.flush()
            await catalog_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.asyncio
async def test_publication_service_is_atomic_when_validation_fails(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.DIGITAL)
    product.images.clear()
    with pytest.raises(DomainError) as error:
        await publish_product(catalog_session, product)
    assert error.value.code == "PRODUCT_IMAGE_REQUIRED"
    assert product.status is ProductStatus.DRAFT
    assert product.published_at is None
    assert (
        await catalog_session.scalar(
            select(func.count()).select_from(Product).where(Product.slug == product.slug)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_persisted_book_availability_requires_explicit_async_loading(
    catalog_session: AsyncSession,
) -> None:
    book = await create_and_publish_product(
        catalog_session,
        _product(ProductKind.BOOK),
    )
    await catalog_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    catalog_session.expire(book, ["book"])
    with pytest.raises(RuntimeError, match="Eager-load Product.book"):
        _ = book.is_available
    loaded = await catalog_session.scalar(
        select(Product)
        .where(Product.id == book.id)
        .execution_options(populate_existing=True)
        .options(selectinload(Product.book))
    )
    assert loaded is not None and loaded.is_available


@pytest.mark.asyncio
async def test_product_schema_types_constraints_and_named_indexes(
    catalog_session: AsyncSession,
) -> None:
    connection = await catalog_session.connection()

    def inspect_schema(sync_connection: Connection) -> tuple[dict[str, Any], dict[str, Any]]:
        inspector = inspect(sync_connection)
        products = {item["name"]: item["type"] for item in inspector.get_columns("products")}
        vouchers = {item["name"]: item["type"] for item in inspector.get_columns("product_voucher")}
        return products, vouchers

    product_columns, voucher_columns = await connection.run_sync(inspect_schema)
    assert isinstance(product_columns["price"], BigInteger)
    assert isinstance(product_columns["kind"], String)
    assert isinstance(product_columns["vat_rate"], String)
    assert isinstance(voucher_columns["validity_months"], Integer)


@pytest.mark.asyncio
async def test_catalog_seed_is_idempotent_and_preserves_edits(
    catalog_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = await catalog_session.connection()
    factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(catalog_seed, "SessionFactory", factory)
    assert await catalog_seed.seed_products() == 4
    await catalog_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    product = await catalog_session.scalar(
        select(Product).where(Product.slug == "swiadoma-seksualnosc")
    )
    assert product is not None
    product.short_description = "Wartość zmieniona lokalnie"
    await catalog_session.flush()
    assert await catalog_seed.seed_products() == 0
    assert await catalog_session.scalar(
        select(Product.short_description).where(Product.id == product.id)
    ) == ("Wartość zmieniona lokalnie")
    assert await catalog_session.scalar(select(func.count()).select_from(Product)) == 4


@pytest.mark.asyncio
async def test_category_slugs_and_two_level_hierarchy(catalog_session: AsyncSession) -> None:
    root = await create_category(catalog_session, name="Książki papierowe")
    duplicate = await create_category(catalog_session, name="Książki papierowe")
    child = await create_category(catalog_session, name="Dla rodziców", parent_id=root.id)
    assert root.slug == "ksiazki-papierowe"
    assert duplicate.slug == "ksiazki-papierowe-2"
    assert child.parent_id == root.id

    with pytest.raises(DomainError, match="dwa poziomy"):
        await create_category(catalog_session, name="Za głęboko", parent_id=child.id)

    nested = await catalog_session.begin_nested()
    root.parent_id = child.id
    with pytest.raises(IntegrityError):
        await catalog_session.flush()
    await nested.rollback()


@pytest.mark.asyncio
async def test_many_categories_and_audiences_are_unique_and_counts_ignore_drafts(
    catalog_session: AsyncSession,
) -> None:
    first = Category(name="Kursy PDF", slug="kursy-pdf")
    second = Category(name="Vouchery na wizyty", slug="vouchery-na-wizyty")
    parent = AudienceTag(name="Rodzice", slug="rodzice")
    adults = AudienceTag(name="Dorośli", slug="dorosli")
    catalog_session.add_all([first, second, parent, adults])
    await catalog_session.flush()

    published = _product(ProductKind.DIGITAL)
    published.voucher = None
    published.book = None
    published.audiobook = None
    catalog_session.add(published)
    published.categories = [first, second]
    published.audience_tags = [parent, adults]
    await create_and_publish_product(catalog_session, published)
    draft = Product(
        kind=ProductKind.DIGITAL,
        name="Szkic",
        slug="szkic",
        status=ProductStatus.DRAFT,
    )
    catalog_session.add(draft)
    draft.categories = [first]
    await catalog_session.flush()

    from sensoria.modules.catalog.router import _category_count

    assert await _category_count(catalog_session, first.id) == 1
    assert await _category_count(catalog_session, second.id) == 1

    nested = await catalog_session.begin_nested()
    with pytest.raises(IntegrityError):
        await catalog_session.execute(
            insert(product_categories).values(product_id=published.id, category_id=first.id)
        )
    await nested.rollback()


@pytest.mark.asyncio
async def test_public_product_category_counts_and_sitemap_use_real_database(
    catalog_session: AsyncSession,
) -> None:
    category = Category(name="Książki papierowe", slug="ksiazki-papierowe")
    tag = AudienceTag(name="Rodzice", slug="rodzice")
    catalog_session.add_all([category, tag])
    await catalog_session.flush()
    product = _product(ProductKind.BOOK)
    product.voucher = None
    product.audiobook = None
    product.digital = None
    catalog_session.add(product)
    product.categories = [category]
    product.audience_tags = [tag]
    product.meta_title = "Ręczny tytuł"
    product.meta_description = "Ręczny opis SEO"
    await create_and_publish_product(catalog_session, product)
    assert product.book is not None
    await catalog_session.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(published_at=func.now() - text("interval '1 second'"))
    )
    await append_stock_movement(
        catalog_session,
        product_id=product.id,
        change=-1,
        reason="manual_adjustment",
        operation_key=f"test-adjust:{product.id}",
        actor_id=uuid4(),
        actor_type=ActorType.ADMINISTRATOR,
        note="Testowa korekta stanu.",
    )
    await catalog_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    draft = Product(
        kind=ProductKind.DIGITAL,
        name="Szkic prywatny",
        slug="szkic",
        status=ProductStatus.DRAFT,
        categories=[category],
    )
    catalog_session.add(draft)
    await catalog_session.flush()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield catalog_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/catalog/public/products/{product.slug}")
            detail_response = await client.get(f"/products/{product.slug}")
            category_response = await client.get("/catalog/public/categories/ksiazki-papierowe")
            sitemap_response = await client.get("/catalog/public/sitemap")
            hidden_draft = await client.get("/catalog/public/products/szkic")
        assert response.status_code == 200
        assert detail_response.status_code == 200
        assert detail_response.json()["book"]["stock_quantity"] == 0
        body = response.json()
        assert body["meta_title"] == "Ręczny tytuł"
        assert body["meta_description"] == "Ręczny opis SEO"
        assert body["categories"][0]["slug"] == category.slug
        assert body["audience_tags"] == ["Rodzice"]
        assert body["is_available"] is False
        assert body["vat_rate"] != "EXEMPT"
        assert category_response.json()["published_product_count"] == 1
        assert len(category_response.json()["products"]) == 1
        assert any(
            entry["kind"] == "product" and entry["slug"] == product.slug
            for entry in sitemap_response.json()["entries"]
        )
        assert hidden_draft.status_code == 404
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_catalog_product_detail_exposes_voucher_variant_ids_and_vat(
    catalog_session: AsyncSession,
) -> None:
    voucher = _product(ProductKind.VOUCHER, name="Voucher testowy")
    voucher.vat_rate = VatRate.EXEMPT
    await create_and_publish_product(catalog_session, voucher)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield catalog_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/products/{voucher.slug}")
        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "VOUCHER"
        assert body["vat_rate"] == "EXEMPT"
        assert body["is_available"] is True
        variant = body["voucher"]["variants"][0]
        assert voucher.voucher is not None
        assert variant["id"] == str(voucher.voucher.variants[0].id)
        assert variant["kind"] == "ONLINE"
        assert variant["price"] == 22000
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_digital_product_detail_returns_lowest_price_at_discount_start(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.DIGITAL, name="E-book z historią ceny")
    product.price = 9900
    await create_and_publish_product(catalog_session, product)
    await catalog_session.flush()

    await catalog_session.execute(
        text("SELECT set_config('sensoria.price_write_guard', 'on', true)")
    )
    catalog_session.add(
        PriceHistory(
            product_id=product.id,
            price=9900,
            compare_at_price=None,
            vat_rate=VatRate.RATE_0,
            valid_from=datetime.now(UTC) - timedelta(days=31),
            changed_by=None,
            actor_type=ActorType.SYSTEM,
            reason="Test snapshot przed oknem ceny",
        )
    )
    await catalog_session.flush()
    await catalog_session.execute(
        text("SELECT set_config('sensoria.price_write_guard', 'off', true)")
    )

    product.price = 7900
    product.compare_at_price = 9900
    await catalog_session.flush()

    detail = await get_product_detail(catalog_session, product.slug)
    assert detail is not None
    assert detail.digital is not None
    assert detail.digital.lowest_price_before_discount == 9900
    assert detail.digital.discount_started_at is not None
    assert detail.digital.discount_started_at.tzinfo is not None


@pytest.mark.asyncio
async def test_digital_product_without_discount_has_no_historical_sale_price(
    catalog_session: AsyncSession,
) -> None:
    product = _product(ProductKind.DIGITAL, name="E-book bez obniżki")
    product.price = 7900
    await create_and_publish_product(catalog_session, product)

    detail = await get_product_detail(catalog_session, product.slug)
    assert detail is not None
    assert detail.digital is not None
    assert detail.digital.lowest_price_before_discount is None
    assert detail.digital.discount_started_at is None


def test_seo_fallbacks_and_description_normalization() -> None:
    description = "  <p>Świadoma seksualność &amp; relacje.</p>  "
    assert plain_description(description, fallback="fallback") == "Świadoma seksualność & relacje."
    assert product_meta_title("Świadoma seksualność", None) == "Świadoma seksualność"
    assert product_meta_title("Nazwa", "Ręczny tytuł") == "Ręczny tytuł"
    assert (
        product_meta_description("Nazwa", "Automatyczny opis.", None, None) == "Automatyczny opis."
    )
    assert category_meta_description("Książki", None, None) == "Poznaj kategorię: Książki."
    long_text = "To jest opis złożony z wielu krótkich wyrazów " * 8
    shortened = plain_description(long_text, fallback="fallback")
    assert len(shortened) <= 160
    assert shortened == long_text[:160].rsplit(" ", 1)[0]
    assert "<" not in plain_description("<b>Opis</b>", fallback="fallback")
    assert decimal_price(7900) == "79.00"
