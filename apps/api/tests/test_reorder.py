"""PostgreSQL-backed tests for account reorder and durable cart reports."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import AsyncClient
from sensoria.modules.accounts.models import Customer
from sensoria.modules.catalog.models import (
    Product,
    ProductBook,
    ProductDigital,
    ProductImage,
)
from sensoria.modules.catalog.service import create_and_publish_product
from sensoria.modules.catalog.types import DigitalLabel, ProductKind, ProductStatus
from sensoria.modules.orders.delivery import DELIVERY_SETTING_KEY
from sensoria.modules.orders.models import (
    Cart,
    CartItem,
    CartReorderOperation,
    Order,
    OrderItem,
)
from sensoria.modules.orders.service import reorder_order
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import AuditLog
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.anyio
async def test_reorder_routes_require_authenticated_customer(api_client: AsyncClient) -> None:
    response = await api_client.post(
        f"/orders/{uuid4()}/reorder", headers={"Idempotency-Key": "test-reorder-key-0001"}
    )
    assert response.status_code == 401
    voucher_response = await api_client.post(
        f"/accounts/vouchers/{uuid4()}/reorder",
        headers={"Idempotency-Key": "test-voucher-key-0001"},
    )
    assert voucher_response.status_code == 401
    cookie_path_response = await api_client.post(
        f"/cart/reorder/orders/{uuid4()}",
        headers={"Idempotency-Key": "test-reorder-key-0002"},
    )
    assert cookie_path_response.status_code == 401


@pytest_asyncio.fixture
async def reorder_environment(
    test_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine: AsyncEngine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield factory
            finally:
                if outer.is_active:
                    await outer.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_reorders_use_independent_postgres_transactions(
    test_database_url: str,
) -> None:
    """Two API workers retrying one operation cannot duplicate a cart line."""
    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_size=5, max_overflow=0)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    customer_id = uuid4()
    product = _new_product(ProductKind.DIGITAL)
    order_id = uuid4()
    source_cart_id = uuid4()
    current_cart_id = uuid4()
    current_token = "concurrent-cart-" + uuid4().hex * 2
    try:
        async with factory() as session, session.begin():
            session.add(product)
            await create_and_publish_product(session, product)
            session.add(
                Customer(
                    id=customer_id,
                    email=f"concurrent-{customer_id.hex}@example.test",
                    password_hash="test-hash",
                    first_name="Test",
                    last_name="Klientka",
                )
            )
            session.add_all(
                [
                    Cart(
                        id=source_cart_id,
                        session_token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
                        expires_at=datetime.now(UTC) + timedelta(days=5),
                    ),
                    Cart(
                        id=current_cart_id,
                        session_token_hash=hashlib.sha256(current_token.encode()).hexdigest(),
                        expires_at=datetime.now(UTC) + timedelta(days=5),
                    ),
                ]
            )
            await session.flush()
            session.add(
                Order(
                    id=order_id,
                    cart_id=source_cart_id,
                    customer_id=customer_id,
                    public_number=f"SEN-2026-{uuid4().hex[:12].upper()}",
                    idempotency_key_hash=uuid4().hex * 2,
                    request_hash=uuid4().hex * 2,
                    email=f"concurrent-{customer_id.hex}@example.test",
                    payment_method="test",
                    status="paid",
                    invoice_data={"kind": "private"},
                    calculation_snapshot={},
                    amount_due_grosz=2500,
                )
            )
            await session.flush()
            session.add(
                OrderItem(
                    order_id=order_id,
                    product_id=product.id,
                    quantity=1,
                    unit_price_snapshot=2500,
                    vat_rate_snapshot=VatRate.EXEMPT,
                    item_settlement={"gross_grosz": 2500},
                    product_name_snapshot=product.name,
                )
            )

        async def reorder_once() -> dict[str, object]:
            async with factory() as session:
                _cart, _token, result = await reorder_order(
                    session,
                    customer_id=customer_id,
                    order_id=order_id,
                    cart_token=current_token,
                    idempotency_key="parallel-reorder-operation-0001",
                )
                return result

        first, second = await asyncio.gather(reorder_once(), reorder_once())
        assert first["operation_id"] == second["operation_id"]
        async with factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CartItem)
                    .where(CartItem.cart_id == current_cart_id)
                )
                == 1
            )
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                delete(CartReorderOperation).where(CartReorderOperation.customer_id == customer_id)
            )
            await session.execute(delete(AuditLog).where(AuditLog.actor_id == customer_id))
            await session.execute(delete(CartItem).where(CartItem.cart_id == current_cart_id))
            await session.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
            await session.execute(delete(Order).where(Order.id == order_id))
            await session.execute(
                delete(Cart).where(Cart.id.in_([source_cart_id, current_cart_id]))
            )
            await session.execute(delete(Customer).where(Customer.id == customer_id))
            # Product price history is append-only, so keep this isolated fixture.
        await engine.dispose()


def _new_product(kind: ProductKind, *, stock: int = 5, published: bool = True) -> Product:
    suffix = uuid4().hex[:12]
    product = Product(
        kind=kind,
        name=f"Test reorder {suffix}",
        slug=f"test-reorder-{suffix}",
        short_description="Testowy produkt",
        price=2500,
        vat_rate=VatRate.EXEMPT,
        status=ProductStatus.DRAFT,
        published_at=None,
        images=[ProductImage(url="https://example.invalid/cover.webp", alt="Okładka testowa")],
        voucher=None,
        categories=[],
        audience_tags=[],
        audiobook=None,
        book=None,
        digital=None,
    )
    if kind is ProductKind.BOOK:
        product.book = ProductBook(
            stock_quantity=stock,
            weight_grams=300,
            length_mm=210,
            width_mm=148,
            height_mm=20,
        )
    elif kind is ProductKind.DIGITAL:
        product.digital = ProductDigital(label=DigitalLabel.EBOOK_PDF, file_format="PDF")
    return product


async def _published(
    factory: async_sessionmaker[AsyncSession], product: Product, *, publish: bool = True
) -> Product:
    async with factory() as session, session.begin():
        session.add(product)
        if publish:
            await create_and_publish_product(session, product)
        await session.flush()
    return product


@pytest.mark.asyncio
async def test_reorder_uses_live_stock_preserves_cart_and_retries_idempotently(
    reorder_environment: async_sessionmaker[AsyncSession],
) -> None:
    factory = reorder_environment
    book = await _published(factory, _new_product(ProductKind.BOOK, stock=2))
    digital = await _published(factory, _new_product(ProductKind.DIGITAL))
    unavailable = await _published(factory, _new_product(ProductKind.DIGITAL), publish=False)
    existing = await _published(factory, _new_product(ProductKind.DIGITAL))
    customer_id = uuid4()
    original_token = "orig-cart-token-" + uuid4().hex * 2
    current_token = "current-cart-token-" + uuid4().hex * 2
    original_cart_id = uuid4()
    current_cart_id = uuid4()
    order_id = uuid4()

    async with factory() as session, session.begin():
        session.add(
            AppSetting(
                key=DELIVERY_SETTING_KEY,
                value={
                    "parcel_locker_cost_grosz": 1000,
                    "courier_cost_grosz": 1500,
                    "free_shipping_threshold_grosz": 20000,
                    "incentive_threshold_grosz": 5000,
                    "vat_rate": "RATE_23",
                },
                description="Kontrolowana konfiguracja testowa",
            )
        )
        session.add(
            Customer(
                id=customer_id,
                email=f"customer-{uuid4().hex[:8]}@example.test",
                password_hash="test-hash",
                first_name="Test",
                last_name="Klientka",
            )
        )
        session.add_all(
            [
                Cart(
                    id=original_cart_id,
                    session_token_hash=hashlib.sha256(original_token.encode()).hexdigest(),
                    expires_at=datetime.now(UTC) + timedelta(days=5),
                ),
                Cart(
                    id=current_cart_id,
                    session_token_hash=hashlib.sha256(current_token.encode()).hexdigest(),
                    expires_at=datetime.now(UTC) + timedelta(days=5),
                ),
            ]
        )
        await session.flush()
        session.add(
            Order(
                id=order_id,
                cart_id=original_cart_id,
                customer_id=customer_id,
                public_number=f"SEN-2026-{uuid4().hex[:12].upper()}",
                idempotency_key_hash=uuid4().hex * 2,
                request_hash=uuid4().hex * 2,
                email=f"customer-{uuid4().hex[:8]}@example.test",
                payment_method="test",
                status="paid",
                invoice_data={"kind": "private"},
                calculation_snapshot={"amount_due_grosz": 9000},
                amount_due_grosz=9000,
            )
        )
        await session.flush()
        for product, quantity in ((book, 3), (digital, 1), (unavailable, 1)):
            session.add(
                OrderItem(
                    order_id=order_id,
                    product_id=product.id,
                    variant_id=None,
                    quantity=quantity,
                    unit_price_snapshot=2000,
                    vat_rate_snapshot=VatRate.EXEMPT,
                    item_settlement={"gross_grosz": 2000 * quantity},
                    product_name_snapshot=product.name,
                )
            )
        session.add(
            CartItem(
                cart_id=current_cart_id,
                product_id=existing.id,
                variant_id=None,
                line_key=f"{existing.id}:none",
                quantity=1,
                unit_price_snapshot=2500,
                vat_rate_snapshot=VatRate.EXEMPT,
            )
        )

    async with factory() as session:
        _cart, _token, report = await reorder_order(
            session,
            customer_id=customer_id,
            order_id=order_id,
            cart_token=current_token,
            idempotency_key="reorder-operation-0001",
        )
        lines = cast(list[dict[str, object]], report["lines"])
        added_by_product = {line["product_id"]: line["added_quantity"] for line in lines}
        assert added_by_product[str(book.id)] == 2
        assert added_by_product[str(digital.id)] == 1
        assert added_by_product[str(unavailable.id)] == 0
        assert report["cart_preserved"] is True
        assert any(line["price_changed"] for line in lines)
        operation_id = cast(str, report["operation_id"])

        # The same key returns the committed report and makes no second cart mutation.
        _cart, _token, retry = await reorder_order(
            session,
            customer_id=customer_id,
            order_id=order_id,
            cart_token=current_token,
            idempotency_key="reorder-operation-0001",
        )
        assert retry["operation_id"] == operation_id

        # If the first HTTP response (and its cookie) was lost, retrying with
        # the same key recovers the same cart and report without applying lines again.
        recovered_cart, recovered_token, recovered = await reorder_order(
            session,
            customer_id=customer_id,
            order_id=order_id,
            cart_token=None,
            idempotency_key="reorder-operation-0001",
        )
        assert recovered["operation_id"] == operation_id
        assert recovered_cart.id == current_cart_id
        assert (
            hashlib.sha256(recovered_token.encode()).hexdigest()
            == recovered_cart.session_token_hash
        )

        count = int(
            await session.scalar(
                select(func.count())
                .select_from(CartItem)
                .where(CartItem.cart_id == current_cart_id)
            )
            or 0
        )
        assert count == 3
        assert (
            await session.scalar(
                select(CartReorderOperation.id).where(CartReorderOperation.id == operation_id)
            )
            is not None
        )


@pytest.mark.asyncio
async def test_reorder_refuses_another_customers_order(
    reorder_environment: async_sessionmaker[AsyncSession],
) -> None:
    factory = reorder_environment
    customer_id = uuid4()
    other_customer_id = uuid4()
    token = "order-owner-test-" + uuid4().hex * 2
    cart_id = uuid4()
    order_id = uuid4()
    async with factory() as session, session.begin():
        for identifier in (customer_id, other_customer_id):
            session.add(
                Customer(
                    id=identifier,
                    email=f"{identifier.hex}@example.test",
                    password_hash="test-hash",
                    first_name="Test",
                    last_name="Osoba",
                )
            )
        session.add(
            Cart(
                id=cart_id,
                session_token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.flush()
        session.add(
            Order(
                id=order_id,
                cart_id=cart_id,
                customer_id=other_customer_id,
                public_number=f"SEN-2026-{uuid4().hex[:12].upper()}",
                idempotency_key_hash=uuid4().hex * 2,
                request_hash=uuid4().hex * 2,
                email="other@example.test",
                payment_method="test",
                status="paid",
                invoice_data={"kind": "private"},
                calculation_snapshot={},
                amount_due_grosz=100,
            )
        )
    async with factory() as session:
        with pytest.raises(DomainError) as error:
            await reorder_order(
                session,
                customer_id=customer_id,
                order_id=order_id,
                cart_token=token,
                idempotency_key="another-customer-key",
            )
    assert error.value.code == "ORDER_NOT_FOUND"
