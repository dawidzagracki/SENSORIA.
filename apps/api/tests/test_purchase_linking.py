"""PostgreSQL tests for verified guest-purchase attachment."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sensoria.modules.accounts.address_fingerprint import address_fingerprint
from sensoria.modules.accounts.models import (
    Customer,
    CustomerAddress,
    CustomerBillingProfile,
)
from sensoria.modules.accounts.purchase_linking import (
    _safe_address,
    reconcile_guest_purchases,
)
from sensoria.modules.orders.models import Cart, Order
from sensoria.shared.audit_log import AuditLog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker


def test_address_normalization_is_exact_beyond_whitespace_and_case() -> None:
    first = _safe_address(
        {"street": "  Leśna   2/4 ", "postal_code": "10-001", "city": " Olsztyn "}
    )
    same = _safe_address({"street": "leśna 2/4", "postal_code": "10-001", "city": "olsztyn"})
    other_flat = _safe_address({"street": "Leśna 2/5", "postal_code": "10-001", "city": "Olsztyn"})
    assert first is not None and same is not None and other_flat is not None
    assert address_fingerprint("address", first) == address_fingerprint("address", same)
    assert address_fingerprint("address", first) != address_fingerprint("address", other_flat)
    assert _safe_address({"street": "Leśna 2", "city": "Olsztyn"}) is None


@pytest.mark.asyncio
async def test_verified_reconciliation_is_scoped_idempotent_and_transactional(
    postgres_client: tuple[Any, Any],
) -> None:
    _client, engine = postgres_client
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    target_id = uuid4()
    other_id = uuid4()
    order_ids: list[Any] = []
    cart_ids: list[Any] = []

    async with factory() as session, session.begin():
        target = Customer(
            id=target_id,
            email="anna@example.test",
            password_hash="not-used-in-this-test",
            first_name="Anna",
            last_name="Testowa",
        )
        other = Customer(
            id=other_id,
            email="other@example.test",
            password_hash="not-used-in-this-test",
            first_name="Inna",
            last_name="Osoba",
            email_verified_at=now,
        )
        session.add_all([target, other])
        await session.flush()

        async def add_order(
            *,
            status: str,
            email: str,
            cart_owner: Any = None,
            shipping: dict[str, Any] | None = None,
        ) -> Order:
            cart = Cart(
                customer_id=cart_owner,
                session_token_hash=uuid4().hex if cart_owner is None else None,
                expires_at=now + timedelta(days=30) if cart_owner is None else None,
            )
            session.add(cart)
            await session.flush()
            cart_ids.append(cart.id)
            order = Order(
                cart_id=cart.id,
                idempotency_key_hash=uuid4().hex,
                request_hash=uuid4().hex,
                email=email,
                payment_method="test",
                status=status,
                invoice_data={
                    "kind": "company",
                    "company_name": "Firma Testowa",
                    "nip": "5260250995",
                    "address": {"street": "Leśna 2/4", "postal_code": "10-001", "city": "Olsztyn"},
                },
                shipping_data=shipping,
                calculation_snapshot={},
                amount_due_grosz=1000,
            )
            session.add(order)
            await session.flush()
            order_ids.append(order.id)
            return order

        eligible = await add_order(
            status="paid",
            email="Anna@Example.test",
            shipping={
                "method": "courier",
                "address": {"street": "Leśna 2/4", "postal_code": "10-001", "city": "Olsztyn"},
            },
        )
        await add_order(status="pending_payment", email="anna@example.test")
        await add_order(status="cancelled", email="anna@example.test")
        await add_order(status="paid", email="anna@example.test", cart_owner=other_id)
        # A point destination must never be imported as a personal address.
        await add_order(
            status="paid",
            email="anna@example.test",
            shipping={
                "method": "parcel_locker",
                "address": {"street": "Locker", "city": "Olsztyn"},
            },
        )

    try:
        async with factory() as session, session.begin():
            result = await reconcile_guest_purchases(
                session, target_id, source="password_login", at=now
            )
            assert result.orders_linked == 0
            assert result.conflicts == 0

        async with factory() as session, session.begin():
            loaded_customer = await session.get(Customer, target_id)
            assert loaded_customer is not None
            loaded_customer.email_verified_at = now

        async with factory() as session, session.begin():
            result = await reconcile_guest_purchases(
                session, target_id, source="email_verification", at=now
            )
            assert result.orders_linked == 2
            assert result.conflicts == 1
            assert result.addresses_added == 1
            assert result.billing_profiles_added == 1
            assert result.vouchers_linked == 0
            assert result.entitlements_linked == 0

        async with factory() as session, session.begin():
            eligible_row = await session.get(Order, eligible.id)
            assert eligible_row is not None and eligible_row.customer_id == target_id
            linked_again = await reconcile_guest_purchases(
                session, target_id, source="password_login", at=now
            )
            assert linked_again.orders_linked == 0
            addresses = (
                await session.scalars(
                    select(CustomerAddress).where(CustomerAddress.customer_id == target_id)
                )
            ).all()
            profiles = (
                await session.scalars(
                    select(CustomerBillingProfile).where(
                        CustomerBillingProfile.customer_id == target_id
                    )
                )
            ).all()
            assert len(addresses) == 1
            assert len(profiles) == 1 and profiles[0].kind == "company"

        async with factory() as session, session.begin():
            cart = Cart(
                session_token_hash=uuid4().hex,
                expires_at=now + timedelta(days=30),
            )
            session.add(cart)
            await session.flush()
            late_order = Order(
                cart_id=cart.id,
                idempotency_key_hash=uuid4().hex,
                request_hash=uuid4().hex,
                email="anna@example.test",
                payment_method="test",
                status="paid",
                invoice_data={"kind": "private"},
                calculation_snapshot={},
                amount_due_grosz=1000,
            )
            session.add(late_order)
            await session.flush()
            order_ids.append(late_order.id)
            cart_ids.append(cart.id)

        # Concurrent invocations use separate PostgreSQL sessions/transactions.
        async def reconcile() -> int:
            async with factory() as session, session.begin():
                result = await reconcile_guest_purchases(
                    session, target_id, source="password_login", at=now
                )
                return result.orders_linked

        outcomes = await asyncio.gather(reconcile(), reconcile())
        assert sorted(outcomes) == [0, 1]

        # A failure before commit leaves the order unattached.
        rollback_order_id = uuid4()
        async with factory() as session, session.begin():
            cart = Cart(
                session_token_hash=uuid4().hex,
                expires_at=now + timedelta(days=30),
            )
            session.add(cart)
            await session.flush()
            order = Order(
                id=rollback_order_id,
                cart_id=cart.id,
                idempotency_key_hash=uuid4().hex,
                request_hash=uuid4().hex,
                email="anna@example.test",
                payment_method="test",
                status="paid",
                invoice_data={
                    "kind": "private",
                    "buyer_snapshot": {"first_name": "Anna", "last_name": "Testowa"},
                },
                calculation_snapshot={},
                amount_due_grosz=1000,
            )
            session.add(order)
            await session.flush()
            order_ids.append(order.id)
            cart_ids.append(cart.id)
        async with factory() as session:
            await session.begin()
            await reconcile_guest_purchases(session, target_id, source="manual", at=now)
            await session.rollback()
        async with factory() as session:
            rolled_back = await session.get(Order, rollback_order_id)
            assert rolled_back is not None and rolled_back.customer_id is None
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                delete(AuditLog).where(AuditLog.entity_id.in_([target_id, other_id]))
            )
            await session.execute(
                delete(CustomerAddress).where(
                    CustomerAddress.customer_id.in_([target_id, other_id])
                )
            )
            await session.execute(
                delete(CustomerBillingProfile).where(
                    CustomerBillingProfile.customer_id.in_([target_id, other_id])
                )
            )
            if order_ids:
                await session.execute(delete(Order).where(Order.id.in_(order_ids)))
            if cart_ids:
                await session.execute(delete(Cart).where(Cart.id.in_(cart_ids)))
            await session.execute(delete(Customer).where(Customer.id.in_([target_id, other_id])))
