"""PostgreSQL integration tests for guest carts and merge primitives."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient, Response
from sensoria.database import get_session
from sensoria.main import app
from sensoria.modules.accounts.models import CustomerConsent
from sensoria.modules.catalog.models import (
    Product,
    ProductBook,
    ProductDigital,
    ProductImage,
    ProductVoucher,
    ProductVoucherVariant,
)
from sensoria.modules.catalog.service import create_and_publish_product
from sensoria.modules.catalog.types import DigitalLabel, ProductKind, VoucherVariantKind
from sensoria.modules.orders import pickup_points
from sensoria.modules.orders import router as orders_router
from sensoria.modules.orders.checkout import normalize_nip
from sensoria.modules.orders.cleanup import delete_expired_guest_carts
from sensoria.modules.orders.delivery import DELIVERY_SETTING_KEY
from sensoria.modules.orders.models import Cart, CartItem, DiscountCode, Order, OrderConsent
from sensoria.modules.orders.schemas import PickupPointSnapshot
from sensoria.modules.orders.service import merge_guest_cart_after_login, record_paid_discount_use
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
CartEnvironment = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


@pytest_asyncio.fixture
async def cart_environment(
    test_database_url: str,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    await asyncio.to_thread(command.upgrade, Config(str(API_ROOT / "alembic.ini")), "head")
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory.begin() as session:
                session.add(
                    AppSetting(
                        key=DELIVERY_SETTING_KEY,
                        value={
                            "parcel_locker_cost_grosz": 1200,
                            "courier_cost_grosz": 1800,
                            "free_shipping_threshold_grosz": 15000,
                            "incentive_threshold_grosz": 5000,
                            "vat_rate": "RATE_23",
                        },
                        description="Testowa, fikcyjna konfiguracja dostawy.",
                    )
                )

            async def override_session() -> AsyncIterator[AsyncSession]:
                async with factory() as session:
                    yield session

            app.dependency_overrides[get_session] = override_session
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="https://cart-test"
                ) as client:
                    yield client, factory
            finally:
                app.dependency_overrides.pop(get_session, None)
                if outer.is_active:
                    await outer.rollback()
    finally:
        await engine.dispose()


def _product(
    kind: ProductKind,
    *,
    price: int = 7900,
    stock: int = 5,
    vat_rate: VatRate = VatRate.EXEMPT,
    voucher_price: int = 9500,
) -> Product:
    product = Product(
        kind=kind,
        name=f"Produkt {kind.value} {uuid4().hex[:7]}",
        slug=f"produkt-{kind.value.lower()}-{uuid4().hex[:10]}",
        short_description="Opis",
        price=price,
        vat_rate=vat_rate,
        images=[ProductImage(url="https://example.invalid/item.webp", alt="Produkt")],
        voucher=None,
        book=None,
        audiobook=None,
        digital=None,
        categories=[],
        audience_tags=[],
    )
    if kind is ProductKind.BOOK:
        product.book = ProductBook(
            stock_quantity=stock,
            weight_grams=320,
            length_mm=210,
            width_mm=148,
            height_mm=22,
        )
    elif kind is ProductKind.VOUCHER:
        product.voucher = ProductVoucher(
            service_name="Konsultacja",
            variants=[ProductVoucherVariant(kind=VoucherVariantKind.ONLINE, price=voucher_price)],
        )
    elif kind is ProductKind.DIGITAL:
        product.digital = ProductDigital(label=DigitalLabel.EBOOK_PDF, file_format="PDF")
    return product


async def _publish(factory: async_sessionmaker[AsyncSession], product: Product) -> Product:
    async with factory() as session, session.begin():
        session.add(product)
        await create_and_publish_product(session, product)
        await session.flush()
    return product


@pytest.mark.asyncio
async def test_delivery_api_quotes_book_and_hides_shipping_for_digital(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    digital = await _publish(factory, _product(ProductKind.DIGITAL, price=20000))
    book = await _publish(factory, _product(ProductKind.BOOK, price=10000, stock=5))

    digital_response = await client.post(
        "/cart/items", json={"product_id": str(digital.id), "quantity": 1}
    )
    assert digital_response.status_code == 200
    digital_body = digital_response.json()
    assert digital_body["item_count"] == 1
    assert digital_body["items"][0]["line_total_grosz"] == 20000
    assert digital_body["items"][0]["image"] == {
        "url": "https://example.invalid/item.webp",
        "alt": "Produkt",
    }
    assert digital_body["items"][0]["vat_label"] == "zw."
    assert digital_body["delivery"]["requires_shipping"] is False
    assert digital_body["delivery"]["available_quotes"] == []
    assert digital_body["delivery"]["message"] is None
    assert digital_body["calculation"]["delivery"]["gross_grosz"] == 0
    assert digital_body["calculation"]["amount_due_is_final"] is True

    token = _cookie(digital_response)
    headers = {"Cookie": f"cart_token={token}"}
    book_response = await client.post(
        "/cart/items",
        json={"product_id": str(book.id), "quantity": 1},
        headers=headers,
    )
    body = book_response.json()
    assert body["item_count"] == 2
    assert (
        next(item for item in body["items"] if item["product_id"] == str(book.id))["details"]
        == "Książka papierowa"
    )
    assert body["delivery"]["requires_shipping"] is True
    assert body["delivery"]["threshold_basis_grosz"] == 30000
    assert body["delivery"]["free_shipping_qualified"] is True
    assert body["delivery"]["requires_method_selection"] is True
    assert body["calculation"]["amount_due_is_final"] is False

    chosen = await client.patch("/cart/delivery", json={"method": "courier"}, headers=headers)
    assert chosen.status_code == 200
    chosen_body = chosen.json()
    assert chosen_body["delivery"]["selected_method"] == "courier"
    assert chosen_body["delivery"]["available_quotes"][0]["gross_grosz"] == 0
    assert chosen_body["calculation"]["delivery"]["vat_rate"] == "RATE_23"
    assert chosen_body["calculation"]["amount_due_grosz"] == 30000
    assert chosen_body["calculation"]["amount_due_is_final"] is True

    book_item_id = next(
        item["id"] for item in chosen_body["items"] if item["product_id"] == str(book.id)
    )
    removed = await client.delete(f"/cart/items/{book_item_id}", headers=headers)
    assert removed.status_code == 200
    removed_body = removed.json()
    assert removed_body["item_count"] == 1
    assert removed_body["delivery"]["requires_shipping"] is False
    assert removed_body["delivery"]["selected_method"] is None
    assert removed_body["calculation"]["delivery"]["gross_grosz"] == 0
    assert removed_body["calculation"]["amount_due_grosz"] == 20000


@pytest.mark.asyncio
async def test_delivery_cost_settings_discount_and_dynamic_reload(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=14999, stock=5))
    response = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    token = _cookie(response)
    headers = {"Cookie": f"cart_token={token}"}
    under = await client.patch("/cart/delivery", json={"method": "parcel_locker"}, headers=headers)
    under_body = under.json()
    assert under_body["delivery"]["remaining_amount_grosz"] == 1
    assert under_body["delivery"]["show_incentive"] is True
    assert under_body["delivery"]["message"] == "Do darmowej dostawy brakuje Ci 0,01 zł"
    assert under_body["calculation"]["delivery"]["gross_grosz"] == 1200
    assert under_body["calculation"]["amount_due_grosz"] == 16199
    assert under_body["calculation"]["delivery"]["tax_grosz"] == 224

    async with factory() as session, session.begin():
        session.add(
            DiscountCode(
                code="DELIVERY10",
                type="percentage",
                value=10,
                min_order_value=0,
                is_active=True,
            )
        )
    discounted = await client.post("/cart/discount", json={"code": "DELIVERY10"}, headers=headers)
    discounted_body = discounted.json()
    assert discounted_body["calculation"]["products_gross_grosz"] == 13499
    assert discounted_body["delivery"]["free_shipping_qualified"] is False
    assert discounted_body["calculation"]["delivery"]["gross_grosz"] == 1200
    assert discounted_body["calculation"]["amount_due_grosz"] == 14699

    removed = await client.delete("/cart/discount", headers=headers)
    assert removed.json()["delivery"]["free_shipping_qualified"] is False
    assert removed.json()["calculation"]["amount_due_grosz"] == 16199

    async with factory() as session, session.begin():
        setting = await session.scalar(
            select(AppSetting).where(AppSetting.key == DELIVERY_SETTING_KEY)
        )
        assert setting is not None
        setting.value = {
            **setting.value,
            "parcel_locker_cost_grosz": 350,
            "free_shipping_threshold_grosz": 17000,
            "incentive_threshold_grosz": 6000,
        }
    reloaded = await client.get("/cart", headers=headers)
    assert reloaded.json()["delivery"]["free_shipping_threshold_grosz"] == 17000
    assert reloaded.json()["delivery"]["remaining_amount_grosz"] == 2001
    assert reloaded.json()["calculation"]["delivery"]["gross_grosz"] == 350


@pytest.mark.asyncio
async def test_pickup_point_selection_persists_verified_snapshot_and_clears_on_method_change(
    cart_environment: CartEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=10000, stock=5))
    added = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    token = _cookie(added)
    headers = {"Cookie": f"cart_token={token}"}
    selected = await client.patch(
        "/cart/delivery", json={"method": "parcel_locker"}, headers=headers
    )
    assert selected.status_code == 200
    assert selected.json()["delivery_point"] is None

    point = PickupPointSnapshot(
        code="OLS01M",
        name="InPost Paczkomat OLS01M",
        street="ul. Przykładowa 8",
        postal_code="10-001",
        city="Olsztyn",
        opening_hours="24/7",
        point_types=["parcel_locker"],
        functions=["parcel_collect"],
        status="Operating",
        verified_at=datetime.now(UTC),
    )

    async def fake_get_point(code: str, settings: object = None) -> PickupPointSnapshot:
        assert code.upper() == "OLS01M"
        return point

    monkeypatch.setattr(pickup_points, "get_point", fake_get_point)
    response = await client.post("/cart/pickup-point", json={"code": "ols01m"}, headers=headers)
    assert response.status_code == 200
    saved = response.json()["delivery_point"]
    assert saved["code"] == "OLS01M"
    assert saved["street"] == "ul. Przykładowa 8"
    assert saved["postal_code"] == "10-001"
    assert saved["city"] == "Olsztyn"
    assert saved["opening_hours"] == "24/7"
    assert saved["status"] == "Operating"
    assert saved["operator"] == "inpost"
    assert saved["verified_at"]

    courier = await client.patch("/cart/delivery", json={"method": "courier"}, headers=headers)
    assert courier.status_code == 200
    assert courier.json()["delivery_point"] is None


@pytest.mark.asyncio
async def test_checkout_revalidates_and_freezes_pickup_point_snapshot(
    cart_environment: CartEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=10000, stock=5))
    async with factory.begin() as session:
        consent_setting = await session.scalar(
            select(AppSetting).where(AppSetting.key == "orders.checkout.consents.v1")
        )
        test_consents = {
            "version": "test-v1",
            "terms": "Akceptuję regulamin.",
            "digital": "Wyrażam zgodę na natychmiastowe wydanie.",
            "marketing": "Zgoda marketingowa.",
        }
        if consent_setting is None:
            session.add(
                AppSetting(
                    key="orders.checkout.consents.v1",
                    value=test_consents,
                    description="Testowy snapshot tekstów checkoutu.",
                )
            )
        else:
            consent_setting.value = test_consents
    added = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    token = _cookie(added)
    headers = {"Cookie": f"cart_token={token}"}
    await client.patch("/cart/delivery", json={"method": "parcel_locker"}, headers=headers)
    point = PickupPointSnapshot(
        code="OLS01APP",
        name="InPost Paczkomat OLS01APP",
        street="Kołobrzeska 6",
        postal_code="10-443",
        city="Olsztyn",
        opening_hours="24/7",
        point_types=["parcel_locker"],
        functions=["parcel_collect"],
        status="Operating",
        verified_at=datetime.now(UTC),
    )

    async def fake_get_point(code: str, settings: object = None) -> PickupPointSnapshot:
        assert code == "OLS01APP"
        return point

    monkeypatch.setattr(pickup_points, "get_point", fake_get_point)
    await client.post("/cart/pickup-point", json={"code": point.code}, headers=headers)
    monkeypatch.setattr(orders_router, "get_point", fake_get_point)
    payload = {
        "email": "guest@example.com",
        "first_name": "Anna",
        "last_name": "Testowa",
        "phone": "+48123123123",
        "delivery_method": "parcel_locker",
        "invoice_kind": "private",
        "payment_method": "blik",
        "terms_accepted": True,
        "consent_version": "test-v1",
    }
    response = await client.post(
        "/cart/checkout",
        json=payload,
        headers={**headers, "Idempotency-Key": "pickup-checkout-test"},
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]
    async with factory() as session:
        order = await session.get(Order, UUID(order_id))
        assert order is not None
        assert order.delivery_point_snapshot is not None
        assert order.delivery_point_snapshot["code"] == "OLS01APP"
        assert order.delivery_point_snapshot["opening_hours"] == "24/7"
        assert order.delivery_point_snapshot["verified_at"]


@pytest.mark.asyncio
async def test_invalid_delivery_settings_fail_closed_before_book_is_added(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=5000, stock=3))
    async with factory() as session, session.begin():
        setting = await session.scalar(
            select(AppSetting).where(AppSetting.key == DELIVERY_SETTING_KEY)
        )
        assert setting is not None
        setting.value = {**setting.value, "vat_rate": "NOT_A_VAT_RATE"}

    response = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    assert response.status_code == 503
    assert "Ustawienia" in response.json()["error"]["message"]
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Cart)) == 0


def _cookie(response: Response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie["cart_token"]
    assert morsel["httponly"]
    assert morsel["secure"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/api/cart"
    expiry = parsedate_to_datetime(morsel["expires"])
    assert datetime.now(UTC) + timedelta(days=29) < expiry < datetime.now(UTC) + timedelta(days=31)
    return morsel.value


@pytest.mark.asyncio
async def test_guest_cart_crud_cookie_and_server_side_snapshots(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    product = await _publish(factory, _product(ProductKind.BOOK, price=8400, stock=4))

    empty = await client.get("/cart")
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["expires_at"] is None
    assert empty.json()["calculation"]["products_gross_grosz"] == 0
    assert empty.json()["calculation"]["amount_due_grosz"] == 0
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Cart)) == 0

    added = await client.post(
        "/cart/items",
        json={"product_id": str(product.id), "quantity": 1, "price": 1},
    )
    assert added.status_code == 422  # unknown price fields are forbidden
    added = await client.post("/cart/items", json={"product_id": str(product.id), "quantity": 2})
    assert added.status_code == 200
    token = _cookie(added)
    headers = {"Cookie": f"cart_token={token}"}
    assert token not in added.text
    first_item = added.json()["items"][0]
    assert first_item["unit_price_snapshot"] == 8400
    assert first_item["vat_rate_snapshot"] == "EXEMPT"
    assert first_item["quantity"] == 2
    read = await client.get("/cart", headers=headers)
    assert read.json()["items"][0]["id"] == first_item["id"]
    other_cart = await client.post(
        "/cart/items", json={"product_id": str(product.id), "quantity": 1}
    )
    other_headers = {"Cookie": f"cart_token={_cookie(other_cart)}"}
    assert (
        await client.patch(
            f"/cart/items/{first_item['id']}", json={"quantity": 4}, headers=other_headers
        )
    ).status_code == 404
    assert (
        await client.delete(f"/cart/items/{first_item['id']}", headers=other_headers)
    ).status_code == 404

    from sensoria.modules.catalog.price_history import price_change_context

    async with (
        factory() as session,
        price_change_context(
            session, actor_type=ActorType.SYSTEM, actor_id=None, reason="Test koszyka"
        ),
    ):
        stored = await session.get(Product, product.id)
        assert stored is not None
        stored.price = 9900
        await session.commit()
    changed = await client.patch(
        f"/cart/items/{first_item['id']}", json={"quantity": 3}, headers=headers
    )
    assert changed.status_code == 200
    assert changed.json()["items"][0]["unit_price_snapshot"] == 8400
    assert changed.json()["items"][0]["quantity"] == 3
    assert changed.json()["calculation"]["items"][0]["gross_grosz"] == 25200
    assert changed.json()["calculation"]["items"][0]["vat_rate"] == "EXEMPT"

    foreign_item = uuid4()
    assert (await client.delete(f"/cart/items/{foreign_item}", headers=headers)).status_code == 404
    assert (
        await client.delete(f"/cart/items/{first_item['id']}", headers=headers)
    ).status_code == 200
    cleared = await client.delete("/cart", headers=headers)
    assert cleared.status_code == 200 and cleared.json()["items"] == []
    assert cleared.json()["calculation"]["amount_due_grosz"] == 0
    async with factory() as session:
        cart = await session.scalar(
            select(Cart)
            .where(Cart.session_token_hash.is_not(None), Cart.customer_id.is_(None))
            .where(Cart.session_token_hash == hashlib.sha256(token.encode("ascii")).hexdigest())
        )
        assert cart is not None
        await session.execute(
            update(Cart)
            .where(Cart.id == cart.id)
            .values(expires_at=func.now() - text("interval '1 second'"))
        )
        await session.commit()
    expired = await client.get("/cart", headers=headers)
    assert expired.json()["items"] == []
    assert expired.json()["expires_at"] is None
    assert expired.json()["calculation"]["amount_due_grosz"] == 0


@pytest.mark.asyncio
async def test_discount_endpoint_validates_and_returns_server_calculation(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    product = await _publish(
        factory,
        _product(ProductKind.BOOK, price=7900, stock=8, vat_rate=VatRate.RATE_5),
    )
    added = await client.post("/cart/items", json={"product_id": str(product.id), "quantity": 1})
    token = _cookie(added)
    headers = {"Cookie": f"cart_token={token}"}
    async with factory() as session:
        code = DiscountCode(
            code="  WIOSNA10  ",
            type="percentage",
            value=10,
            min_order_value=7900,
            max_uses=1,
        )
        session.add(code)
        session.add(
            DiscountCode(code="MINIMUM", type="fixed_amount", value=100, min_order_value=8000)
        )
        await session.commit()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(DiscountCode(code="wiosna10", type="percentage", value=10))
                await session.flush()

    applied = await client.post("/cart/discount", json={"code": " wiosna10 "}, headers=headers)
    assert applied.status_code == 200
    body = applied.json()
    assert body["discount_code"] == "WIOSNA10"
    assert body["calculation"]["products_gross_before_discount_grosz"] == 7900
    assert body["calculation"]["discount_grosz"] == 790
    assert body["calculation"]["products_gross_grosz"] == 7110

    invalid = await client.post("/cart/discount", json={"code": "missing"}, headers=headers)
    assert invalid.status_code == 400
    below_minimum = await client.post("/cart/discount", json={"code": "minimum"}, headers=headers)
    assert below_minimum.status_code == 400
    unchanged = await client.get("/cart", headers=headers)
    assert unchanged.json()["discount_code"] == "WIOSNA10"
    assert unchanged.json()["calculation"]["discount_grosz"] == 790

    removed = await client.delete("/cart/discount", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["discount_code"] is None
    assert removed.json()["calculation"]["discount_grosz"] == 0
    assert removed.json()["calculation"]["products_gross_grosz"] == 7900
    reapplied = await client.post("/cart/discount", json={"code": "wiosna10"}, headers=headers)
    assert reapplied.status_code == 200
    emptied = await client.delete(f"/cart/items/{body['items'][0]['id']}", headers=headers)
    assert emptied.status_code == 200
    assert emptied.json()["discount_code"] is None
    assert "usunięty" in emptied.json()["discount_notice"]
    assert emptied.json()["calculation"]["discount_grosz"] == 0
    async with factory() as session:
        stored = await session.get(DiscountCode, code.id)
        assert stored is not None and stored.used_count == 0
        cart = await session.scalar(select(Cart))
        assert cart is not None
        order = Order(
            cart_id=cart.id,
            idempotency_key_hash="1" * 64,
            request_hash="2" * 64,
            email="buyer@example.com",
            payment_method="blik",
            invoice_data={"kind": "private"},
            calculation_snapshot={},
            amount_due_grosz=0,
        )
        session.add(order)
        await session.flush()
        order_id = order.id
        async with session.begin_nested():
            assert await record_paid_discount_use(
                session, discount_code_id=code.id, order_id=order_id
            )
        await session.commit()
    async with factory() as session:
        async with session.begin():
            assert not await record_paid_discount_use(
                session, discount_code_id=code.id, order_id=order_id
            )
        await session.commit()
    async with factory() as session:
        with pytest.raises(DomainError, match="Limit użyć"):
            async with session.begin():
                await record_paid_discount_use(session, discount_code_id=code.id, order_id=uuid4())


@pytest.mark.asyncio
async def test_product_rules_deduplication_and_voucher_lines(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, stock=3))
    digital = await _publish(factory, _product(ProductKind.DIGITAL))
    voucher = await _publish(factory, _product(ProductKind.VOUCHER))
    other_voucher = await _publish(factory, _product(ProductKind.VOUCHER))
    draft = _product(ProductKind.DIGITAL)
    async with factory() as session, session.begin():
        session.add(draft)
        await session.flush()
    token_response = await client.post(
        "/cart/items", json={"product_id": str(book.id), "quantity": 2}
    )
    headers = {"Cookie": f"cart_token={_cookie(token_response)}"}
    assert (
        await client.post(
            "/cart/items", json={"product_id": str(draft.id), "quantity": 1}, headers=headers
        )
    ).status_code == 409
    assert (
        await client.post(
            "/cart/items", json={"product_id": str(book.id), "quantity": 2}, headers=headers
        )
    ).status_code == 409
    assert (
        await client.post(
            "/cart/items", json={"product_id": str(digital.id), "quantity": 2}, headers=headers
        )
    ).status_code == 422
    for _ in range(2):
        response = await client.post(
            "/cart/items", json={"product_id": str(digital.id), "quantity": 1}, headers=headers
        )
        assert response.status_code == 200
    assert sum(item["product_id"] == str(digital.id) for item in response.json()["items"]) == 1
    assert voucher.voucher is not None
    variant_id = str(voucher.voucher.variants[0].id)
    assert other_voucher.voucher is not None
    wrong_variant = await client.post(
        "/cart/items",
        json={
            "product_id": str(voucher.id),
            "variant_id": str(other_voucher.voucher.variants[0].id),
            "quantity": 1,
        },
        headers=headers,
    )
    assert wrong_variant.status_code == 422
    for _ in range(2):
        response = await client.post(
            "/cart/items",
            json={"product_id": str(voucher.id), "variant_id": variant_id, "quantity": 1},
            headers=headers,
        )
        assert response.status_code == 200
    assert sum(item["product_id"] == str(voucher.id) for item in response.json()["items"]) == 2
    assert all(
        item["unit_price_snapshot"] == 9500
        for item in response.json()["items"]
        if item["product_id"] == str(voucher.id)
    )


@pytest.mark.asyncio
async def test_cart_api_returns_snapshot_based_mixed_vat_calculation(
    cart_environment: CartEnvironment,
) -> None:
    client, _factory = cart_environment
    digital = await _publish(
        _factory, _product(ProductKind.DIGITAL, price=7900, vat_rate=VatRate.RATE_5)
    )
    voucher = await _publish(
        _factory,
        _product(ProductKind.VOUCHER, vat_rate=VatRate.EXEMPT, voucher_price=25000),
    )
    assert voucher.voucher is not None
    book = await _publish(
        _factory, _product(ProductKind.BOOK, price=5900, stock=2, vat_rate=VatRate.RATE_5)
    )

    first = await client.post("/cart/items", json={"product_id": str(digital.id), "quantity": 1})
    cookie = _cookie(first)
    headers = {"Cookie": f"cart_token={cookie}"}
    assert first.status_code == 200
    assert (
        await client.post(
            "/cart/items",
            json={
                "product_id": str(voucher.id),
                "variant_id": str(voucher.voucher.variants[0].id),
                "quantity": 1,
            },
            headers=headers,
        )
    ).status_code == 200
    response = await client.post(
        "/cart/items",
        json={"product_id": str(book.id), "quantity": 2},
        headers=headers,
    )
    assert response.status_code == 200
    calculation = response.json()["calculation"]
    assert sorted(
        (line["gross_grosz"], line["net_grosz"], line["tax_grosz"]) for line in calculation["items"]
    ) == [(7900, 7524, 376), (11800, 11238, 562), (25000, 25000, 0)]
    assert calculation["products_gross_grosz"] == calculation["amount_due_grosz"] == 44700
    assert calculation["amount_due_is_final"] is False
    assert calculation["exempt"] == {
        "vat_rate": "EXEMPT",
        "vat_label": "zw.",
        "gross_grosz": 25000,
        "net_grosz": 25000,
        "tax_grosz": 0,
    }
    group = next(item for item in calculation["vat_groups"] if item["vat_rate"] == "RATE_5")
    assert (group["gross_grosz"], group["net_grosz"], group["tax_grosz"]) == (
        19700,
        18762,
        938,
    )


@pytest.mark.asyncio
async def test_guest_merge_preserves_snapshots_and_retries_are_idempotent(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=8400, stock=8))
    guest_response = await client.post(
        "/cart/items", json={"product_id": str(book.id), "quantity": 2}
    )
    token = _cookie(guest_response)
    customer_id = uuid4()
    async with factory() as session, session.begin():
        account = Cart(customer_id=customer_id)
        session.add(account)
        await session.flush()
        session.add(
            CartItem(
                cart_id=account.id,
                product_id=book.id,
                variant_id=None,
                line_key=f"{book.id}:none",
                quantity=1,
                unit_price_snapshot=9900,
                vat_rate_snapshot=VatRate.RATE_23,
            )
        )
    async with factory() as session:
        result = await merge_guest_cart_after_login(
            session, guest_token=token, authenticated_customer_id=customer_id
        )
        assert result.merged
        assert not result.conflicts
        assert len(result.conditions_changed) == 1
        assert result.conditions_changed[0].product_id == book.id
        assert result.conditions_changed[0].account_price_snapshot == 9900
        assert result.conditions_changed[0].guest_price_snapshot == 8400
        retry = await merge_guest_cart_after_login(
            session, guest_token=token, authenticated_customer_id=customer_id
        )
        assert retry.merged is False
    async with factory() as session:
        persisted_account = await session.scalar(
            select(Cart).where(Cart.customer_id == customer_id)
        )
        assert persisted_account is not None
        items = list(
            (
                await session.scalars(
                    select(CartItem).where(CartItem.cart_id == persisted_account.id)
                )
            ).all()
        )
        assert len(items) == 1
        assert items[0].quantity == 3
        assert items[0].unit_price_snapshot == 9900
        assert items[0].vat_rate_snapshot is VatRate.RATE_23
    guest_view = await client.get("/cart", headers={"Cookie": f"cart_token={token}"})
    assert guest_view.json()["items"] == []


@pytest.mark.asyncio
async def test_merge_stock_conflict_rolls_back_and_cleanup_is_bounded(
    cart_environment: CartEnvironment,
) -> None:
    _client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, stock=4))
    token = ""
    async with factory() as session:
        from sensoria.modules.orders.service import add_item

        _guest, token = await add_item(
            session, None, product_id=book.id, variant_id=None, quantity=3
        )
        account = Cart(customer_id=uuid4())
        session.add(account)
        await session.flush()
        session.add(
            CartItem(
                cart_id=account.id,
                product_id=book.id,
                variant_id=None,
                line_key=f"{book.id}:none",
                quantity=3,
                unit_price_snapshot=book.price,
                vat_rate_snapshot=book.vat_rate,
            )
        )
        account_id = account.customer_id
        await session.commit()
    assert account_id is not None
    async with factory() as session:
        outcome = await merge_guest_cart_after_login(
            session, guest_token=token, authenticated_customer_id=account_id
        )
        assert not outcome.merged
        assert outcome.conflicts[0].available_quantity == 1
    async with factory() as session:
        guest = await session.scalar(
            select(Cart).where(Cart.session_token_hash.is_not(None), Cart.customer_id.is_(None))
        )
        assert guest is not None
        account_cart = await session.scalar(select(Cart).where(Cart.customer_id == account_id))
        assert account_cart is not None
        account_item = await session.scalar(
            select(CartItem).where(CartItem.cart_id == account_cart.id)
        )
        assert account_item is not None and account_item.quantity == 3
        await session.execute(
            update(Cart)
            .where(Cart.id == guest.id)
            .values(expires_at=func.now() - text("interval '31 days'"))
        )
        session.add_all(
            [
                Cart(
                    session_token_hash="e" * 64,
                    expires_at=func.now() - text("interval '31 days'"),
                ),
                Cart(
                    session_token_hash="f" * 64,
                    expires_at=func.now() + text("interval '1 day'"),
                ),
            ]
        )
        await session.commit()
    deleted = await delete_expired_guest_carts(factory, batch_size=1)
    assert deleted == 1
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(Cart).where(Cart.customer_id == account_id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(Cart).where(Cart.customer_id.is_(None))
            )
            == 2
        )
    assert await delete_expired_guest_carts(factory, batch_size=1) == 1
    async with factory() as session:
        remaining_guest = await session.scalar(
            select(func.count()).select_from(Cart).where(Cart.customer_id.is_(None))
        )
        assert remaining_guest == 1


def test_nip_checksum_and_separator_normalization() -> None:
    assert normalize_nip("856-734-62-15") == "8567346215"
    with pytest.raises(DomainError, match="sumę kontrolną"):
        normalize_nip("8567346216")
    with pytest.raises(DomainError, match="10-cyfrowy NIP"):
        normalize_nip("12345")


@pytest.mark.asyncio
async def test_guest_checkout_is_idempotent_and_records_consents(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    digital = await _publish(
        factory, _product(ProductKind.DIGITAL, price=7900, vat_rate=VatRate.RATE_5)
    )
    added = await client.post("/cart/items", json={"product_id": str(digital.id), "quantity": 1})
    assert added.status_code == 200
    token = _cookie(added)
    config_response = await client.get("/cart/checkout-config")
    assert config_response.status_code == 200
    config = config_response.json()
    payload = {
        "email": "buyer@example.com",
        "invoice_kind": "private",
        "payment_method": "blik",
        "terms_accepted": True,
        "digital_consent": True,
        "marketing_consent": False,
        "consent_version": config["consent_version"],
        "issuance_mode": "immediate",
    }
    headers = {"Idempotency-Key": "checkout-test-key", "Cookie": f"cart_token={token}"}
    first = await client.post("/cart/checkout", json=payload, headers=headers)
    second = await client.post("/cart/checkout", json=payload, headers=headers)
    changed_payload = {**payload, "email": "other@example.com"}
    conflicting_retry = await client.post("/cart/checkout", json=changed_payload, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["order_id"] == second.json()["order_id"]
    assert conflicting_retry.status_code == 409
    assert first.json()["status"] == "pending_payment"
    assert first.json()["payment_url"] is None
    async with factory() as session:
        order = await session.scalar(select(Order).where(Order.id == first.json()["order_id"]))
        assert order is not None
        consents = list(
            (
                await session.scalars(select(OrderConsent).where(OrderConsent.order_id == order.id))
            ).all()
        )
        assert order.amount_due_grosz == 7900
        assert order.calculation_snapshot["items"][0]["vat_rate"] == "RATE_5"
        assert {consent.kind: consent.granted for consent in consents} == {
            "terms": True,
            "digital": True,
            "marketing": False,
        }
        privacy_events = list(
            (
                await session.scalars(
                    select(CustomerConsent).where(
                        CustomerConsent.order_consent_id.in_(
                            select(OrderConsent.id).where(OrderConsent.order_id == order.id)
                        )
                    )
                )
            ).all()
        )
        assert len(privacy_events) == 3
        assert {event.source for event in privacy_events} == {"checkout"}
        assert {event.consent_type for event in privacy_events} == {
            "checkout_terms",
            "checkout_digital",
            "checkout_marketing",
        }
        assert all(
            event.consent_text_id and event.ip_hash and event.subject_digest
            for event in privacy_events
        )


@pytest.mark.asyncio
async def test_checkout_rejects_missing_digital_consent_without_order(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    digital = await _publish(
        factory, _product(ProductKind.DIGITAL, price=7900, vat_rate=VatRate.RATE_5)
    )
    added = await client.post("/cart/items", json={"product_id": str(digital.id), "quantity": 1})
    token = _cookie(added)
    config = (await client.get("/cart/checkout-config")).json()
    payload = {
        "email": "buyer@example.com",
        "invoice_kind": "private",
        "payment_method": "blik",
        "terms_accepted": True,
        "digital_consent": False,
        "marketing_consent": False,
        "consent_version": config["consent_version"],
        "issuance_mode": "immediate",
    }
    response = await client.post(
        "/cart/checkout",
        json=payload,
        headers={
            "Idempotency-Key": "missing-consent",
            "Cookie": f"cart_token={token}",
        },
    )
    assert response.status_code == 422
    assert "zgoda" in response.json()["error"]["message"].lower()
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.asyncio
async def test_checkout_rejects_changed_price_without_creating_order(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    digital = await _publish(factory, _product(ProductKind.DIGITAL, price=7900))
    added = await client.post("/cart/items", json={"product_id": str(digital.id), "quantity": 1})
    token = _cookie(added)
    config = (await client.get("/cart/checkout-config")).json()
    async with factory() as session, session.begin():
        product = await session.get(Product, digital.id)
        assert product is not None
        product.price = 8900
    response = await client.post(
        "/cart/checkout",
        json={
            "email": "buyer@example.com",
            "payment_method": "blik",
            "terms_accepted": True,
            "digital_consent": True,
            "consent_version": config["consent_version"],
        },
        headers={"Idempotency-Key": "changed-price", "Cookie": f"cart_token={token}"},
    )
    assert response.status_code == 409
    assert "zmieniły się" in response.json()["error"]["message"]
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.asyncio
async def test_checkout_reserves_last_book_across_guest_carts(
    cart_environment: CartEnvironment,
) -> None:
    client, factory = cart_environment
    book = await _publish(factory, _product(ProductKind.BOOK, price=10000, stock=1))
    first_cart = await client.post("/cart/items", json={"product_id": str(book.id), "quantity": 1})
    first_token = _cookie(first_cart)
    second_cart = await client.post(
        "/cart/items",
        json={"product_id": str(book.id), "quantity": 1},
        headers={"Cookie": f"cart_token={uuid4().hex}{uuid4().hex}"},
    )
    # The intentionally unknown token gets a new isolated guest cart.
    second_token = _cookie(second_cart)
    config = (await client.get("/cart/checkout-config")).json()
    payload = {
        "email": "buyer@example.com",
        "first_name": "Anna",
        "last_name": "Testowa",
        "phone": "123456789",
        "delivery_method": "courier",
        "shipping_address": {"street": "Testowa 1", "postal_code": "10-001", "city": "Olsztyn"},
        "payment_method": "blik",
        "terms_accepted": True,
        "consent_version": config["consent_version"],
    }
    first = await client.post(
        "/cart/checkout",
        json=payload,
        headers={"Idempotency-Key": "reserve-first", "Cookie": f"cart_token={first_token}"},
    )
    second = await client.post(
        "/cart/checkout",
        json=payload,
        headers={"Idempotency-Key": "reserve-second", "Cookie": f"cart_token={second_token}"},
    )
    assert first.status_code == 201
    assert first.json()["status"] == "pending_payment"
    assert second.status_code == 409
    assert "egzemplarzy" in second.json()["error"]["message"]
    detail = await client.get(f"/products/{book.slug}")
    assert detail.status_code == 200
    assert detail.json()["book"]["stock_quantity"] == 1
    assert detail.json()["book"]["available_quantity"] == 0
    assert detail.json()["is_available"] is False
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Order)) == 1
