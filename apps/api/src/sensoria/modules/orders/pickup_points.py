"""InPost Points API adapter and guest-cart point selection."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import Settings, get_settings
from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.types import ProductKind
from sensoria.shared.errors import DomainError

from .models import Cart, CartItem
from .schemas import PickupPointListResponse, PickupPointQuery, PickupPointSnapshot
from .service import _token_digest

POINTS_API = "https://api-pl-points.easypack24.net/v1/points"
POINT_CODE_RE = re.compile(r"^[A-Z0-9]{3,20}$")
POSTAL_CODE_RE = re.compile(r"^\d{2}-?\d{3}$")


class PickupPointPreferenceStore(Protocol):
    """Future [59] adapter contract; guest email is never an identity key."""

    async def get_recent(self, customer_id: str) -> PickupPointSnapshot | None: ...

    async def save_recent(self, customer_id: str, point: PickupPointSnapshot) -> None: ...


def _request_json(url: str, timeout: float) -> dict[str, Any]:
    """Make a bounded GET to the fixed official InPost Points host."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "SensoriaShop/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed allow-listed host
        if response.status != 200:
            raise OSError("InPost Points API returned a non-200 response")
        payload = json.loads(response.read(1_000_000))
    if not isinstance(payload, dict):
        raise ValueError("Invalid InPost response")
    return payload


def _safe_point(raw: dict[str, Any]) -> PickupPointSnapshot | None:
    """Accept only operating parcel lockers that support parcel collection."""
    name = raw.get("name")
    types = raw.get("type")
    functions = raw.get("functions")
    address = raw.get("address_details")
    if (
        not isinstance(name, str)
        or not POINT_CODE_RE.fullmatch(name)
        or raw.get("status") != "Operating"
        or not isinstance(types, list)
        or "parcel_locker" not in types
        or not isinstance(functions, list)
        or "parcel_collect" not in functions
        or not isinstance(address, dict)
    ):
        return None
    street = address.get("street")
    building = address.get("building_number")
    postal_code = address.get("post_code")
    city = address.get("city")
    if not (
        isinstance(street, str)
        and street.strip()
        and isinstance(postal_code, str)
        and postal_code.strip()
        and isinstance(city, str)
        and city.strip()
    ):
        return None
    if isinstance(building, str) and building.strip():
        street = f"{street} {building}"
    return PickupPointSnapshot(
        code=name,
        name=str(raw.get("display_name") or f"InPost Paczkomat {name}"),
        street=street,
        postal_code=postal_code,
        city=city,
        opening_hours=(
            raw.get("opening_hours") if isinstance(raw.get("opening_hours"), str) else None
        ),
        point_types=types,
        functions=functions,
        status="Operating",
        verified_at=datetime.now(UTC),
    )


async def _fetch(
    url: str, settings: Settings, *, missing_point_is_invalid: bool = False
) -> dict[str, Any]:
    """Retry one transient failure with strict timeouts and safe errors."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return await asyncio.to_thread(
                _request_json, url, float(settings.INPOST_POINTS_TIMEOUT_SECONDS)
            )
        except HTTPError as error:
            if error.code == 404 and missing_point_is_invalid:
                raise DomainError(
                    "INPOST_POINT_UNAVAILABLE",
                    "Nie znaleziono czynnego Paczkomatu obsługującego odbiór przesyłek.",
                    422,
                ) from None
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.1)
        except (URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.1)
    raise DomainError(
        "INPOST_POINTS_UNAVAILABLE",
        "Nie można teraz potwierdzić punktu InPost. Spróbuj ponownie.",
        503,
    ) from last_error


async def search_points(query: str, settings: Settings | None = None) -> PickupPointListResponse:
    """Search points by city or postal code using fixed query parameters."""
    try:
        value = PickupPointQuery(query=query.strip()).query
    except ValidationError:
        raise DomainError("INPOST_QUERY_INVALID", "Podaj miasto albo kod pocztowy.", 422) from None
    params: dict[str, str] = {
        "type": "parcel_locker",
        "functions": "parcel_collect",
        "per_page": "20",
        "page": "1",
    }
    if POSTAL_CODE_RE.fullmatch(value):
        params["post_code"] = value
    else:
        params["city"] = value
    data = await _fetch(f"{POINTS_API}?{urlencode(params)}", settings or get_settings())
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise DomainError(
            "INPOST_POINTS_UNAVAILABLE", "Otrzymano nieprawidłową odpowiedź InPost.", 503
        )
    points = [_safe_point(item) for item in raw_items if isinstance(item, dict)]
    return PickupPointListResponse(items=[point for point in points if point is not None])


async def get_point(code: str, settings: Settings | None = None) -> PickupPointSnapshot:
    """Load and validate one point; never use a client-provided URL."""
    normalized = code.strip().upper()
    if not POINT_CODE_RE.fullmatch(normalized):
        raise DomainError("INPOST_POINT_INVALID", "Podaj prawidłowy kod Paczkomatu.", 422)
    data = await _fetch(
        f"{POINTS_API}/{normalized}",
        settings or get_settings(),
        missing_point_is_invalid=True,
    )
    point = _safe_point(data)
    if point is None:
        raise DomainError(
            "INPOST_POINT_UNAVAILABLE",
            "Nie znaleziono czynnego Paczkomatu obsługującego odbiór przesyłek.",
            422,
        )
    return point


async def _current_cart(session: AsyncSession, token: str | None) -> Cart:
    if token is None or not 40 <= len(token) <= 128:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
    try:
        digest = _token_digest(token)
    except UnicodeEncodeError:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404) from None
    cart = await session.scalar(
        select(Cart).where(
            Cart.session_token_hash == digest,
            Cart.customer_id.is_(None),
            Cart.expires_at > func.now(),
        )
    )
    if cart is None:
        raise DomainError("CART_NOT_FOUND", "Nie znaleziono aktywnego koszyka.", 404)
    if cart.delivery_method != "parcel_locker":
        raise DomainError("PICKUP_METHOD_REQUIRED", "Najpierw wybierz Paczkomat InPost.", 409)
    has_book = await session.scalar(
        select(CartItem.id)
        .join(Product, Product.id == CartItem.product_id)
        .where(CartItem.cart_id == cart.id, Product.kind == ProductKind.BOOK)
    )
    if has_book is None:
        raise DomainError("DELIVERY_NOT_REQUIRED", "Ten koszyk nie wymaga dostawy.", 409)
    return cart


async def list_cart_points(
    session: AsyncSession, token: str | None, query: str
) -> PickupPointListResponse:
    await _current_cart(session, token)
    await session.rollback()
    return await search_points(query)


async def choose_cart_point(
    session: AsyncSession, token: str | None, code: str
) -> PickupPointSnapshot:
    """Resolve externally first, then persist the verified snapshot under cart lock."""
    await _current_cart(session, token)
    await session.rollback()
    point = await get_point(code)
    assert token is not None
    digest = _token_digest(token)
    async with session.begin():
        cart = await session.scalar(
            select(Cart)
            .where(
                Cart.session_token_hash == digest,
                Cart.customer_id.is_(None),
                Cart.expires_at > func.now(),
            )
            .with_for_update()
        )
        if cart is None:
            raise DomainError("CART_NOT_FOUND", "Koszyk wygasł lub nie istnieje.", 404)
        if cart.delivery_method != "parcel_locker":
            raise DomainError("PICKUP_METHOD_REQUIRED", "Najpierw wybierz Paczkomat InPost.", 409)
        cart.delivery_point_snapshot = point.model_dump(mode="json")
        await session.flush()
    return point
