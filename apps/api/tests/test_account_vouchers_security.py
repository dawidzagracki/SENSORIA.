"""Account voucher routes fail closed until trusted customer authentication exists."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.accounts.vouchers import _safe_booking_url
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_voucher_account_endpoints_require_authenticated_principal(
    api_client: AsyncClient,
) -> None:
    voucher_id = uuid4()
    responses = [
        await api_client.get("/accounts/vouchers"),
        await api_client.get(f"/accounts/vouchers/{voucher_id}/qr"),
        await api_client.get(f"/accounts/vouchers/{voucher_id}/pdf"),
        await api_client.post(
            f"/accounts/vouchers/{voucher_id}/extension-requests",
            json={"message": "Proszę o przedłużenie terminu."},
        ),
        await api_client.get("/accounts/shipments"),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401]
    for response in responses:
        assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_client_identity_fields_do_not_replace_authentication(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(
        "/accounts/vouchers", params={"email": "owner@example.test", "customer_id": str(uuid4())}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_customer_shipment_contract_queries_postgres_and_is_private(
    postgres_client: tuple[AsyncClient, AsyncEngine],
) -> None:
    from sensoria.main import app

    client, _engine = postgres_client
    app.dependency_overrides[require_customer_id] = lambda: uuid4()
    try:
        response = await client.get("/accounts/shipments")
    finally:
        app.dependency_overrides.pop(require_customer_id, None)

    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://sensoria.example/rezerwacja", "https://sensoria.example/rezerwacja"),
        ("javascript:alert(1)", None),
        ("//evil.example/path", None),
        ("https://user:pass@example.test/path", None),
        ("https://[invalid/path", None),
        (None, None),
    ],
)
def test_booking_url_comes_only_from_safe_http_configuration(
    value: object, expected: str | None
) -> None:
    assert _safe_booking_url(value) == expected
