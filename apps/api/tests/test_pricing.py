"""Gross price calculations and PostgreSQL-backed price-history behavior."""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.price_history import (
    PriceHistory,
    lowest_price_last_30_days,
    price_change_context,
)
from sensoria.modules.catalog.schemas import ProductDraftInput
from sensoria.modules.catalog.types import ProductKind
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.pricing import split_gross_price, vat_label
from sensoria.shared.types import VatRate
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest.mark.parametrize(
    ("rate", "net", "tax", "label"),
    [
        (VatRate.RATE_23, 6423, 1477, "23%"),
        (VatRate.RATE_8, 7315, 585, "8%"),
        (VatRate.RATE_5, 7524, 376, "5%"),
        (VatRate.RATE_0, 7900, 0, "0%"),
        (VatRate.EXEMPT, 7900, 0, "zw."),
    ],
)
def test_split_gross_price_7900_grosz(rate: VatRate, net: int, tax: int, label: str) -> None:
    result = split_gross_price(7900, rate)
    assert (result.gross_grosz, result.net_grosz, result.tax_grosz) == (7900, net, tax)
    assert result.vat_rate is rate
    assert result.vat_label == label
    assert result.net_grosz + result.tax_grosz == result.gross_grosz


def test_random_gross_amounts_always_reconcile_exactly() -> None:
    generator = random.Random(4815162342)
    rates = tuple(VatRate)
    for _ in range(1000):
        gross = generator.randrange(0, 10_000_000)
        for rate in rates:
            result = split_gross_price(gross, rate)
            assert result.net_grosz + result.tax_grosz == gross


def test_tax_labels_distinguish_zero_rate_from_exemption() -> None:
    assert vat_label(VatRate.RATE_0) == "0%"
    assert vat_label(VatRate.EXEMPT) == "zw."


@pytest.mark.parametrize("compare", [7899, 7900])
def test_product_input_rejects_compare_at_price_not_above_price(compare: int) -> None:
    with pytest.raises(ValueError, match="Cena porównawcza musi być wyższa"):
        ProductDraftInput(kind=ProductKind.DIGITAL, price=7900, compare_at_price=compare)


def test_product_input_allows_missing_or_greater_compare_at_price() -> None:
    assert ProductDraftInput(kind=ProductKind.DIGITAL, price=7900).compare_at_price is None
    assert (
        ProductDraftInput(
            kind=ProductKind.DIGITAL, price=7900, compare_at_price=7901
        ).compare_at_price
        == 7901
    )


@pytest.mark.parametrize("gross", [True, 7900.0, -1])
def test_gross_price_rejects_invalid_amounts(gross: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        split_gross_price(gross, VatRate.RATE_5)  # type: ignore[arg-type]


def _product(slug: str, *, price: int | None = 7900, compare: int | None = None) -> Product:
    return Product(
        kind=ProductKind.DIGITAL,
        name="Produkt testowy",
        slug=slug,
        price=price,
        compare_at_price=compare,
        vat_rate=VatRate.RATE_5,
    )


@pytest_asyncio.fixture
async def price_session(
    postgres_client: tuple[AsyncClient, AsyncEngine],
) -> AsyncIterator[AsyncSession]:
    _client, engine = postgres_client
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
                await session.close()
                if transaction.is_active:
                    await transaction.rollback()


async def _snapshots(session: AsyncSession, product_id: object) -> list[PriceHistory]:
    return list(
        (
            await session.scalars(
                select(PriceHistory)
                .where(PriceHistory.product_id == product_id)
                .order_by(PriceHistory.version)
            )
        ).all()
    )


async def test_create_price_update_tax_and_compare_changes_are_automatic(
    price_session: AsyncSession,
) -> None:
    product = _product(f"price-{uuid4().hex}", compare=9900)
    price_session.add(product)
    await price_session.flush()
    assert product.id is not None
    history = await _snapshots(price_session, product.id)
    assert len(history) == 1
    assert (history[0].price, history[0].compare_at_price, history[0].vat_rate) == (
        7900,
        9900,
        VatRate.RATE_5,
    )
    assert history[0].actor_type is ActorType.SYSTEM
    assert history[0].reason == "Początkowy zapis produktu"

    actor_id = uuid4()
    async with price_change_context(
        price_session,
        actor_type=ActorType.ADMINISTRATOR,
        actor_id=actor_id,
        reason="Zmiana ceny testowej",
    ):
        product.price = 8500
        await price_session.flush()
    product.vat_rate = VatRate.RATE_8
    await price_session.flush()
    product.compare_at_price = 10_000
    await price_session.flush()

    history = await _snapshots(price_session, product.id)
    assert len(history) == 4
    assert len({entry.valid_from for entry in history}) == 1
    assert [entry.version for entry in history] == sorted(entry.version for entry in history)
    assert [entry.price for entry in history] == [7900, 8500, 8500, 8500]
    assert [entry.vat_rate for entry in history] == [
        VatRate.RATE_5,
        VatRate.RATE_5,
        VatRate.RATE_8,
        VatRate.RATE_8,
    ]
    assert history[1].changed_by == actor_id
    assert history[1].actor_type is ActorType.ADMINISTRATOR
    assert history[1].reason == "Zmiana ceny testowej"
    audit = list(
        (
            await price_session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_id == product.id)
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        ).all()
    )
    assert len(audit) == 4
    price_change_audit = next(
        entry for entry in audit if entry.payload["reason"] == "Zmiana ceny testowej"
    )
    assert price_change_audit.actor_id == actor_id
    assert price_change_audit.actor_type is ActorType.ADMINISTRATOR
    assert price_change_audit.payload["reason"] == "Zmiana ceny testowej"
    assert price_change_audit.payload["previous"] == {
        "price": 7900,
        "compare_at_price": 9900,
        "vat_rate": VatRate.RATE_5.value,
    }
    assert price_change_audit.payload["current"]["price"] == 8500


async def test_noop_price_assignment_does_not_add_duplicate(price_session: AsyncSession) -> None:
    product = _product(f"noop-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    product.price = 7900
    await price_session.flush()
    assert len(await _snapshots(price_session, product.id)) == 1


async def test_history_uses_unique_application_uuids_utc_time_and_ordered_versions(
    price_session: AsyncSession,
) -> None:
    products = [_product(f"uuid-{uuid4().hex}") for _ in range(2)]
    price_session.add_all(products)
    await price_session.flush()
    snapshots = [
        entry for product in products for entry in await _snapshots(price_session, product.id)
    ]
    assert len(snapshots) == 2
    assert all(isinstance(entry.id, UUID) for entry in snapshots)
    assert snapshots[0].id != snapshots[1].id
    assert all(entry.valid_from.tzinfo is not None for entry in snapshots)
    assert len({entry.version for entry in snapshots}) == 2


async def test_price_history_and_audit_rollback_with_product(price_session: AsyncSession) -> None:
    slug = f"rollback-{uuid4().hex}"
    product = _product(slug)
    price_session.add(product)
    await price_session.flush()
    assert (
        await price_session.scalar(
            select(func.count())
            .select_from(PriceHistory)
            .where(PriceHistory.product_id == product.id)
        )
        == 1
    )
    assert (
        await price_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == product.id)
        )
        == 1
    )
    await price_session.rollback()
    assert await price_session.scalar(select(Product.id).where(Product.slug == slug)) is None
    assert (
        await price_session.scalar(
            select(func.count())
            .select_from(PriceHistory)
            .where(PriceHistory.product_id == product.id)
        )
        == 0
    )
    assert (
        await price_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == product.id)
        )
        == 0
    )


@pytest.mark.parametrize("compare", [7899, 7900])
async def test_invalid_compare_at_price_rejected(price_session: AsyncSession, compare: int) -> None:
    product = _product(f"invalid-{uuid4().hex}", compare=compare)
    price_session.add(product)
    with pytest.raises(ValueError, match="Cena porównawcza musi być wyższa"):
        await price_session.flush()
    await price_session.rollback()


async def test_database_constraint_rejects_compare_at_price_equal_to_price(
    price_session: AsyncSession,
) -> None:
    product = _product(f"constraint-{uuid4().hex}", compare=9000)
    price_session.add(product)
    await price_session.flush()
    await price_session.execute(text("SELECT set_config('sensoria.price_write_guard', 'on', true)"))
    with pytest.raises(DBAPIError):
        await price_session.execute(
            text("UPDATE products SET price = :price WHERE id = :product_id"),
            {"price": 9000, "product_id": product.id},
        )
    await price_session.rollback()


async def test_compare_price_none_or_greater_allowed_and_price_change_validated(
    price_session: AsyncSession,
) -> None:
    product = _product(f"compare-{uuid4().hex}", compare=None)
    price_session.add(product)
    await price_session.flush()
    product.compare_at_price = 9000
    await price_session.flush()
    product.price = 9000
    with pytest.raises(ValueError, match="Cena porównawcza musi być wyższa"):
        await price_session.flush()
    await price_session.rollback()


async def test_direct_bulk_price_update_is_blocked(price_session: AsyncSession) -> None:
    product = _product(f"bulk-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    with pytest.raises(DBAPIError):
        await price_session.execute(
            update(Product).where(Product.id == product.id).values(price=8000)
        )
    await price_session.rollback()


async def test_history_is_append_only_and_product_delete_is_restricted(
    price_session: AsyncSession,
) -> None:
    product = _product(f"append-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    snapshot = (await _snapshots(price_session, product.id))[0]
    snapshot.reason = "edytowana"
    with pytest.raises(ValueError, match="Historia cen jest dopisywana"):
        await price_session.flush()
    await price_session.rollback()


async def test_history_database_guard_blocks_direct_update_and_product_delete(
    price_session: AsyncSession,
) -> None:
    product = _product(f"db-guard-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    product_id = product.id
    await price_session.commit()
    with pytest.raises(DBAPIError):
        await price_session.execute(
            update(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .values(reason="bezpośrednia edycja")
        )
    await price_session.rollback()
    with pytest.raises(DBAPIError):
        await price_session.execute(
            delete(PriceHistory).where(PriceHistory.product_id == product_id)
        )
    await price_session.rollback()
    with pytest.raises(DBAPIError):
        await price_session.execute(
            text("UPDATE products SET price = :price WHERE id = :product_id"),
            {"price": 8100, "product_id": product_id},
        )
    await price_session.rollback()

    loaded_product = await price_session.get(Product, product_id)
    assert loaded_product is not None
    await price_session.delete(loaded_product)
    with pytest.raises(DBAPIError):
        await price_session.flush()
    await price_session.rollback()


async def test_lowest_price_window_edges_and_opening_snapshot(
    price_session: AsyncSession,
) -> None:
    product = _product(f"window-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    at = start + timedelta(days=30)
    rows = [
        PriceHistory(
            product_id=product.id,
            price=7900,
            compare_at_price=None,
            vat_rate=VatRate.RATE_5,
            valid_from=start - timedelta(days=45),
            actor_type=ActorType.SYSTEM,
            reason="wartość obowiązująca na początku",
        ),
        PriceHistory(
            product_id=product.id,
            price=3000,
            compare_at_price=None,
            vat_rate=VatRate.RATE_5,
            valid_from=start,
            actor_type=ActorType.SYSTEM,
            reason="granica początku okna",
        ),
        PriceHistory(
            product_id=product.id,
            price=3200,
            compare_at_price=None,
            vat_rate=VatRate.RATE_5,
            valid_from=start,
            actor_type=ActorType.SYSTEM,
            reason="kolejna wersja w tej samej chwili",
        ),
        PriceHistory(
            product_id=product.id,
            price=4000,
            compare_at_price=9000,
            vat_rate=VatRate.RATE_5,
            valid_from=start + timedelta(days=5),
            actor_type=ActorType.SYSTEM,
            reason="zmiana w oknie",
        ),
        PriceHistory(
            product_id=product.id,
            price=1000,
            compare_at_price=None,
            vat_rate=VatRate.RATE_5,
            valid_from=at,
            actor_type=ActorType.SYSTEM,
            reason="dokładnie na końcu, poza oknem",
        ),
        PriceHistory(
            product_id=product.id,
            price=500,
            compare_at_price=None,
            vat_rate=VatRate.RATE_5,
            valid_from=at + timedelta(seconds=1),
            actor_type=ActorType.SYSTEM,
            reason="przyszły wpis",
        ),
    ]
    price_session.add_all(rows)
    await price_session.flush()
    assert await lowest_price_last_30_days(price_session, product.id, at) == 3200
    assert (
        await lowest_price_last_30_days(price_session, product.id, start + timedelta(days=4))
        == 3000
    )
    assert (
        await lowest_price_last_30_days(price_session, product.id, start - timedelta(days=46))
        is None
    )
    with pytest.raises(ValueError, match="strefę czasową"):
        await lowest_price_last_30_days(price_session, product.id, datetime(2026, 1, 1))


async def test_lowest_price_uses_at_not_wall_clock(price_session: AsyncSession) -> None:
    product = _product(f"at-{uuid4().hex}")
    price_session.add(product)
    await price_session.flush()
    old = datetime(2010, 1, 1, tzinfo=UTC)
    price_session.add(
        PriceHistory(
            product_id=product.id,
            price=1234,
            compare_at_price=None,
            vat_rate=VatRate.EXEMPT,
            valid_from=old,
            actor_type=ActorType.SYSTEM,
            reason="krótka dostępna historia",
        )
    )
    await price_session.flush()
    assert (
        await lowest_price_last_30_days(price_session, product.id, old + timedelta(days=20)) == 1234
    )
    result = await price_session.scalar(
        select(func.count()).select_from(PriceHistory).where(PriceHistory.product_id == product.id)
    )
    assert result == 2
