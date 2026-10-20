"""Authenticated customer shipment summary for account surfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sensoria.database import get_session
from sensoria.modules.catalog.models import Product, ProductImage
from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.orders.models import Order, OrderItem, Shipment
from sensoria.modules.orders.shipments import (
    TrackingPolicy,
    build_shipment_tracking_url,
    load_tracking_policy,
)
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError

from .auth import require_customer_id

router = APIRouter(prefix="/shipments", tags=["account-shipments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}


class PhysicalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    name: str
    quantity: int
    cover_url: str | None
    cover_alt: str | None


class ShipmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    delivery_method: Literal["parcel_locker", "courier", "pickup_in_person"] | None
    fulfillment_status: str
    shipment_status: str | None
    carrier: str | None
    tracking_number: str | None
    tracking_url: str | None
    tracking_link_status: Literal["available", "not_shipped", "unconfigured"]
    shipped_at: datetime | None
    delivered_at: datetime | None
    pickup_ready_at: datetime | None
    picked_up_at: datetime | None
    pickup_point: dict[str, Any] | None
    shipping_address: dict[str, Any] | None
    pickup_information: str | None
    items: list[PhysicalItem]


class ShipmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ShipmentSummary]


def _safe_address_snapshot(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    keys = ("street", "building_number", "apartment_number", "postal_code", "city")
    return {
        key: clean for key in keys if (clean := _safe_text(value.get(key), 200)) is not None
    } or None


def _safe_pickup_snapshot(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    keys = ("code", "name", "street", "postal_code", "city")
    return {
        key: clean for key in keys if (clean := _safe_text(value.get(key), 200)) is not None
    } or None


def _safe_text(value: Any, limit: int = 500) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())[:limit]
    return clean or None


def _allowed_delivery_method(
    value: Any,
) -> Literal["parcel_locker", "courier", "pickup_in_person"] | None:
    if value in {"parcel_locker", "courier", "pickup_in_person"}:
        return cast(Literal["parcel_locker", "courier", "pickup_in_person"], value)
    return None


async def _load_tracking_policy_or_none(session: AsyncSession) -> TrackingPolicy | None:
    try:
        return await load_tracking_policy(session)
    except DomainError:
        return None


@router.get("", response_model=ShipmentListResponse)
async def list_customer_shipments(
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
) -> ShipmentListResponse:
    """Return all physical lines from this authenticated customer's paid/history orders."""
    response.headers.update(PRIVATE_HEADERS)
    cover_image = aliased(ProductImage)
    first_cover_id = (
        select(cover_image.id)
        .where(cover_image.product_id == Product.id)
        .order_by(cover_image.position, cover_image.id)
        .limit(1)
        .correlate(Product)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(Order, Shipment, OrderItem, Product, ProductImage.url, ProductImage.alt)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .outerjoin(
                ProductImage,
                ProductImage.id == first_cover_id,
            )
            .outerjoin(Shipment, Shipment.order_id == Order.id)
            .where(
                Order.customer_id == customer_id,
                or_(
                    Order.status == "paid",
                    and_(Order.status == "cancelled", Order.fulfillment_status == "cancelled"),
                ),
                Product.kind == ProductKind.BOOK,
            )
            .order_by(Order.created_at.desc(), Order.id, OrderItem.id)
        )
    ).all()
    if not rows:
        return ShipmentListResponse(items=[])

    settings = await session.scalar(select(AppSetting).where(AppSetting.key == "orders.pickup.v1"))
    pickup_configuration = settings.value if settings is not None else {}
    pickup_information = (
        _safe_text(pickup_configuration.get("customer_information"), 1000)
        if isinstance(pickup_configuration, dict)
        else None
    )
    policies: dict[bool, TrackingPolicy | None] = {}
    grouped: dict[UUID, ShipmentSummary] = {}
    for order, shipment, item, product, cover_url, cover_alt in rows:
        summary = grouped.get(order.id)
        if summary is None:
            method = _allowed_delivery_method((order.shipping_data or {}).get("method"))
            point = _safe_pickup_snapshot(order.delivery_point_snapshot)
            address = _safe_address_snapshot((order.shipping_data or {}).get("address"))
            tracking_url = None
            link_status: Literal["available", "not_shipped", "unconfigured"] = "not_shipped"
            if shipment is not None and shipment.status in {"shipped", "delivered"}:
                policy = policies.get(True)
                if True not in policies:
                    policy = await _load_tracking_policy_or_none(session)
                    policies[True] = policy
                if policy is None:
                    link_status = "unconfigured"
                else:
                    tracking_url = build_shipment_tracking_url(
                        policy, shipment.carrier, shipment.tracking_number
                    )
                    link_status = "available" if tracking_url else "unconfigured"
            summary = ShipmentSummary(
                order_id=order.id,
                delivery_method=method,
                fulfillment_status=order.fulfillment_status,
                shipment_status=shipment.status if shipment is not None else None,
                carrier=shipment.carrier if shipment is not None else None,
                tracking_number=shipment.tracking_number if shipment is not None else None,
                tracking_url=tracking_url,
                tracking_link_status=link_status,
                shipped_at=shipment.shipped_at if shipment is not None else None,
                delivered_at=shipment.delivered_at if shipment is not None else None,
                pickup_ready_at=order.pickup_ready_at,
                picked_up_at=order.picked_up_at,
                pickup_point=point,
                shipping_address=address,
                pickup_information=(pickup_information if method == "pickup_in_person" else None),
                items=[],
            )
            grouped[order.id] = summary
        summary.items.append(
            PhysicalItem(
                product_id=product.id,
                name=_safe_text(item.product_name_snapshot, 200)
                or _safe_text(product.name, 200)
                or "Książka papierowa",
                quantity=item.quantity,
                cover_url=_safe_text(cover_url, 2048),
                cover_alt=_safe_text(cover_alt, 500),
            )
        )
    return ShipmentListResponse(items=list(grouped.values()))
