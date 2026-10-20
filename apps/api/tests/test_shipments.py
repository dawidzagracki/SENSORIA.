"""Shipment tracking contracts and PostgreSQL transaction tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sensoria.modules.catalog.models import Product, ProductBook
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.orders.models import (
    Cart,
    Order,
    OrderItem,
    Shipment,
    ShipmentHistory,
    ShipmentNotificationJob,
)
from sensoria.modules.orders.shipments import (
    TrackingPolicy,
    build_shipment_tracking_url,
    build_tracking_url,
    ship_order,
    validate_tracking_number,
)
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import AuditLog
from sensoria.shared.errors import DomainError
from sensoria.shared.types import VatRate
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def test_inpost_format_is_a_warning_not_a_blocker() -> None:
    number, warning = validate_tracking_number("001234567890123456789012")
    assert number == "001234567890123456789012"
    assert warning is None
    unusual, warning = validate_tracking_number("AB-00123")
    assert unusual == "AB-00123"
    assert warning is not None


@pytest.mark.parametrize("value", ["", "  ", "123\n456", "x" * 161])
def test_empty_controls_and_unreasonable_tracking_number_are_rejected(value: str) -> None:
    with pytest.raises(DomainError):
        validate_tracking_number(value)


def test_tracking_number_is_encoded_as_url_component_and_host_is_bound() -> None:
    policy = TrackingPolicy.model_validate(
        {
            "carriers": {
                "carrier-a": {
                    "label": "Carrier A",
                    "template": "https://tracking.example/parcel/{tracking_number}",
                    "host": "tracking.example",
                }
            }
        }
    )
    assert (
        build_tracking_url(policy, "carrier-a", "AA/0012")
        == "https://tracking.example/parcel/AA%2F0012"
    )


def test_customer_tracking_url_resolves_the_stored_carrier_label_through_settings() -> None:
    policy = TrackingPolicy.model_validate(
        {
            "carriers": {
                "inpost": {
                    "label": "InPost",
                    "template": "https://tracking.example/parcel/{tracking_number}",
                    "host": "tracking.example",
                }
            }
        }
    )
    assert (
        build_shipment_tracking_url(policy, "InPost", "0012/34")
        == "https://tracking.example/parcel/0012%2F34"
    )
    assert build_shipment_tracking_url(policy, "Unknown", "123") is None


def test_tracking_policy_rejects_unsafe_scheme() -> None:
    policy = TrackingPolicy.model_validate(
        {
            "carriers": {
                "bad": {
                    "label": "Bad",
                    "template": "javascript:alert(1)/{tracking_number}",
                    "host": "example.invalid",
                }
            }
        }
    )
    with pytest.raises(DomainError):
        build_tracking_url(policy, "bad", "123")


@pytest.mark.asyncio
async def test_admin_shipment_routes_require_authenticated_admin(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/admin/orders/00000000-0000-0000-0000-000000000001/ship",
        json={"carrier": "inpost", "tracking_number": "001234567890123456789012"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ADMIN_AUTHENTICATION_REQUIRED"


def test_parallel_shipment_attempts_create_one_record_and_notice(test_database_url: str) -> None:
    """Independent sessions serialize the operation on PostgreSQL's order row lock."""

    async def run() -> None:
        engine = create_async_engine(test_database_url, pool_size=5, max_overflow=0)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        cart_id, product_id, order_id, item_id = (uuid4() for _ in range(4))
        actor_id = uuid4()
        async with factory() as session, session.begin():
            # Insert through SQL so the product price-history ORM hook does not
            # leave immutable fixture history in the shared integration database.
            await session.execute(
                text("SELECT set_config('sensoria.price_write_guard', 'on', true)")
            )
            await session.execute(
                insert(Product).values(
                    id=product_id,
                    kind=ProductKind.BOOK,
                    name="Fixture book",
                    slug=f"fixture-book-{product_id}",
                )
            )
            await session.execute(
                insert(ProductBook).values(
                    product_id=product_id,
                    stock_quantity=0,
                    low_stock_threshold=0,
                )
            )
            session.add_all(
                [
                    Cart(
                        id=cart_id,
                        session_token_hash="a" * 64,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        delivery_method="courier",
                    ),
                    Order(
                        id=order_id,
                        cart_id=cart_id,
                        idempotency_key_hash="b" * 64,
                        request_hash="c" * 64,
                        email="fixture@example.invalid",
                        payment_method="test",
                        status="paid",
                        fulfillment_status="awaiting_fulfillment",
                        invoice_data={"kind": "private"},
                        shipping_data={"method": "courier"},
                        calculation_snapshot={"version": 1},
                        amount_due_grosz=100,
                    ),
                    OrderItem(
                        id=item_id,
                        order_id=order_id,
                        product_id=product_id,
                        quantity=1,
                        unit_price_snapshot=100,
                        vat_rate_snapshot=VatRate.RATE_23,
                        item_settlement={"gross_grosz": 100},
                    ),
                    AppSetting(
                        key="orders.shipment_tracking.v1",
                        value={
                            "carriers": {
                                "inpost": {
                                    "label": "InPost",
                                    "template": "https://tracking.example/{tracking_number}",
                                    "host": "tracking.example",
                                }
                            }
                        },
                        description="test only",
                    ),
                ]
            )

        async def attempt() -> Shipment:
            async with factory() as session:
                return await ship_order(
                    session,
                    order_id=order_id,
                    carrier="inpost",
                    tracking_number="001234567890123456789012",
                    actor_id=actor_id,
                )

        first, second = await asyncio.gather(attempt(), attempt())
        assert first.id == second.id
        async with factory() as session:
            assert (
                await session.scalar(
                    select(func.count(Shipment.id)).where(Shipment.order_id == order_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count(ShipmentHistory.id))
                    .join(Shipment)
                    .where(Shipment.order_id == order_id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count(ShipmentNotificationJob.id)).where(
                        ShipmentNotificationJob.order_id == order_id
                    )
                )
                == 1
            )
            shipment = await session.scalar(select(Shipment).where(Shipment.order_id == order_id))
            assert shipment is not None
            await session.execute(
                delete(ShipmentHistory).where(ShipmentHistory.shipment_id == shipment.id)
            )
            await session.execute(
                delete(ShipmentNotificationJob).where(ShipmentNotificationJob.order_id == order_id)
            )
            await session.delete(shipment)
            await session.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
            await session.execute(delete(Order).where(Order.id == order_id))
            await session.execute(delete(Cart).where(Cart.id == cart_id))
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == order_id))
            await session.execute(delete(AuditLog).where(AuditLog.entity_id == shipment.id))
            await session.execute(delete(ProductBook).where(ProductBook.product_id == product_id))
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.execute(
                delete(AppSetting).where(AppSetting.key == "orders.shipment_tracking.v1")
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(run())
