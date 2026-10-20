"""Customer order history authorization and reference behavior."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sensoria.main import app
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.accounts.orders import _order_number
from sensoria.modules.orders.models import Order
from sqlalchemy.ext.asyncio import AsyncEngine


def test_order_number_prefers_persisted_public_reference() -> None:
    order = Order(
        public_number="SEN-2026-0123456789ABCDEF",
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        id=uuid4(),
    )
    assert _order_number(order) == "SEN-2026-0123456789ABCDEF"


def test_legacy_order_has_stable_fallback_reference() -> None:
    identifier = uuid4()
    order = Order(
        public_number=None,
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        id=identifier,
    )
    assert _order_number(order) == f"SEN-2026-{identifier.hex[:8].upper()}"


@pytest.mark.anyio
async def test_order_history_requires_authenticated_customer(api_client: AsyncClient) -> None:
    response = await api_client.get("/accounts/orders")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_authenticated_empty_order_history_runs_against_postgres(
    postgres_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    client, _engine = postgres_client
    customer_id = uuid4()
    app.dependency_overrides[require_customer_id] = lambda: customer_id
    try:
        response = await client.get("/accounts/orders")
    finally:
        app.dependency_overrides.pop(require_customer_id, None)

    assert response.status_code == 200, response.text
    assert response.json()["counts"] == {
        "all": 0,
        "in_progress": 0,
        "completed": 0,
        "invoices": 0,
    }
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
