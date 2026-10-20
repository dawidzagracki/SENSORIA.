"""Adapter tests use controlled InPost responses and make no claim of live connectivity."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from sensoria.modules.orders import pickup_points
from sensoria.modules.orders.schemas import PickupPointSnapshot


def _raw_point(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "name": "OLS01M",
        "display_name": "InPost Paczkomat OLS01M",
        "type": ["parcel_locker"],
        "status": "Operating",
        "functions": ["parcel_collect", "parcel_send"],
        "address_details": {
            "street": "Kętrzyńskiego",
            "building_number": "12",
            "post_code": "10-001",
            "city": "Olsztyn",
        },
        "opening_hours": "24/7",
    }
    value.update(overrides)
    return value


def test_adapter_accepts_operating_collection_locker_and_rejects_other_points() -> None:
    point = pickup_points._safe_point(_raw_point())
    assert point is not None
    assert point.code == "OLS01M"
    assert point.street == "Kętrzyńskiego 12"
    assert point.opening_hours == "24/7"
    assert point.verified_at.tzinfo == UTC

    assert pickup_points._safe_point(_raw_point(status="NonOperating")) is None
    assert pickup_points._safe_point(_raw_point(type=["pop"])) is None
    assert pickup_points._safe_point(_raw_point(functions=["parcel_send"])) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_key", "expected_value"),
    [("Olsztyn", "city", "Olsztyn"), ("10-001", "post_code", "10-001")],
)
async def test_search_uses_fixed_api_and_city_or_postcode_filters(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    expected_key: str,
    expected_value: str,
) -> None:
    urls: list[str] = []

    async def fake_fetch(url: str, _settings: object) -> dict[str, object]:
        urls.append(url)
        return {"items": [_raw_point()]}

    monkeypatch.setattr(pickup_points, "_fetch", fake_fetch)
    result = await pickup_points.search_points(query)

    assert len(result.items) == 1
    parsed = urlsplit(urls[0])
    assert parsed.scheme == "https"
    assert parsed.netloc == "api-pl-points.easypack24.net"
    parameters = parse_qs(parsed.query)
    assert parameters[expected_key] == [expected_value]
    assert parameters["type"] == ["parcel_locker"]
    assert parameters["functions"] == ["parcel_collect"]
    assert "https://" not in query


@pytest.mark.asyncio
async def test_search_does_not_return_unavailable_or_wrong_type_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch(_url: str, _settings: object) -> dict[str, object]:
        return {
            "items": [
                _raw_point(),
                _raw_point(name="OLS02M", status="NonOperating"),
                _raw_point(name="OLS03P", type=["pop"]),
            ]
        }

    monkeypatch.setattr(pickup_points, "_fetch", fake_fetch)
    result = await pickup_points.search_points("Olsztyn")
    assert [point.code for point in result.items] == ["OLS01M"]


def test_snapshot_time_is_timezone_aware() -> None:
    snapshot = PickupPointSnapshot(
        code="OLS01M",
        name="Locker",
        street="Street 1",
        postal_code="10-001",
        city="Olsztyn",
        point_types=["parcel_locker"],
        functions=["parcel_collect"],
        status="Operating",
        verified_at=datetime.now(UTC),
    )
    assert snapshot.verified_at.utcoffset() is not None
