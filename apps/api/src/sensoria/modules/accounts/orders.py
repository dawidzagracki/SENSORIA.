"""Authenticated order history and immutable purchase snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.catalog.models import Product, ProductImage
from sensoria.modules.orders.models import Order, OrderItem, Shipment
from sensoria.modules.orders.shipments import build_shipment_tracking_url, load_tracking_policy
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError

from .auth import require_customer_id
from .models import Customer

router = APIRouter(prefix="/orders", tags=["account-orders"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]
PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Vary": "Cookie, Authorization",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}


class OrderItemSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    product_id: UUID
    name: str
    kind: str
    quantity: int
    unit_price_grosz: int
    line_total_grosz: int
    vat_rate: str
    variant: str | None
    cover_url: str | None
    cover_alt: str | None


class ShipmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: UUID
    delivery_method: str | None
    fulfillment_status: str
    carrier: str | None
    shipment_status: str | None
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
    items: list[dict[str, Any]]


class OrderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    number: str
    created_at: datetime
    status: str
    buyer_email: str
    fulfillment_status: str
    amount_due_grosz: int
    paid_amount_grosz: int | None
    calculation: dict[str, Any]
    invoice: dict[str, Any]
    shipping: dict[str, Any] | None
    delivery_point: dict[str, Any] | None
    items: list[OrderItemSummary]
    shipment: ShipmentSummary | None
    documents: list[dict[str, Any]]


class OrderHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str
    contact_email: str | None
    contact_phone: str | None
    first_purchase_at: datetime | None
    total_count: int
    counts: dict[str, int]
    page: int
    page_size: int
    items: list[OrderSummary]


def _snapshot_text(value: Any, limit: int = 500) -> str | None:
    if not isinstance(value, str):
        return None
    result = " ".join(value.split())[:limit]
    return result or None


def _order_number(order: Order) -> str:
    """Return the persisted public order number or a stable legacy reference."""
    if order.public_number:
        return order.public_number
    year = order.created_at.year
    return f"SEN-{year}-{order.id.hex[:8].upper()}"


def _line_total(item: OrderItem) -> int:
    settlement = item.item_settlement if isinstance(item.item_settlement, dict) else {}
    amount = settlement.get("gross_grosz")
    if isinstance(amount, int) and not isinstance(amount, bool):
        return amount
    return item.unit_price_snapshot * item.quantity


def _variant(item: OrderItem) -> str | None:
    snapshot = item.voucher_snapshot or {}
    kind = snapshot.get("variant_kind")
    if kind == "IN_PERSON":
        return "W gabinecie"
    if kind == "ONLINE":
        return "Online"
    return None


@router.get("", response_model=OrderHistoryResponse)
async def list_customer_orders(
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    status_filter: Annotated[
        Literal["all", "in_progress", "completed", "invoices"], Query(alias="filter")
    ] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> OrderHistoryResponse:
    """List only orders linked to the authenticated customer, with whole-set counts."""
    response.headers.update(PRIVATE_HEADERS)
    base = select(Order).where(Order.customer_id == customer_id)
    in_progress_states = ("pending_payment", "awaiting_fulfillment", "shipped", "ready_for_pickup")
    if status_filter == "in_progress":
        base = base.where(
            (Order.status == "pending_payment")
            | ((Order.status == "paid") & Order.fulfillment_status.in_(in_progress_states[1:]))
        )
    elif status_filter == "completed":
        base = base.where(
            (Order.status == "paid") & Order.fulfillment_status.in_(("delivered", "picked_up"))
        )
    elif status_filter == "invoices":
        # Document generation [36] is not present. The separate documents contract is empty.
        base = base.where(false())

    total = int(await session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    counts = {
        "all": int(
            await session.scalar(
                select(func.count()).select_from(
                    select(Order.id).where(Order.customer_id == customer_id).subquery()
                )
            )
            or 0
        ),
        "in_progress": int(
            await session.scalar(
                select(func.count()).select_from(
                    select(Order.id)
                    .where(
                        Order.customer_id == customer_id,
                        (Order.status == "pending_payment")
                        | (
                            (Order.status == "paid")
                            & Order.fulfillment_status.in_(in_progress_states[1:])
                        ),
                    )
                    .subquery()
                )
            )
            or 0
        ),
        "completed": int(
            await session.scalar(
                select(func.count()).select_from(
                    select(Order.id)
                    .where(
                        Order.customer_id == customer_id,
                        Order.status == "paid",
                        Order.fulfillment_status.in_(("delivered", "picked_up")),
                    )
                    .subquery()
                )
            )
            or 0
        ),
        "invoices": 0,
    }
    order_rows = list(
        (
            await session.scalars(
                base.order_by(Order.created_at.desc(), Order.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    order_ids = [order.id for order in order_rows]
    items_by_order: dict[UUID, list[OrderItemSummary]] = {item: [] for item in order_ids}
    if order_ids:
        rows = (
            await session.execute(
                select(OrderItem, Product, ProductImage.url, ProductImage.alt)
                .join(Product, Product.id == OrderItem.product_id)
                .outerjoin(
                    ProductImage,
                    ProductImage.id
                    == select(ProductImage.id)
                    .where(ProductImage.product_id == Product.id)
                    .order_by(ProductImage.position, ProductImage.id)
                    .limit(1)
                    .correlate(Product)
                    .scalar_subquery(),
                )
                .where(OrderItem.order_id.in_(order_ids))
                .order_by(OrderItem.order_id, OrderItem.id)
            )
        ).all()
        for item, product, cover_url, cover_alt in rows:
            items_by_order[item.order_id].append(
                OrderItemSummary(
                    id=item.id,
                    product_id=item.product_id,
                    name=_snapshot_text(item.product_name_snapshot, 200) or product.name,
                    kind=product.kind.value,
                    quantity=item.quantity,
                    unit_price_grosz=item.unit_price_snapshot,
                    line_total_grosz=_line_total(item),
                    vat_rate=item.vat_rate_snapshot.value,
                    variant=_variant(item),
                    cover_url=_snapshot_text(cover_url, 2048),
                    cover_alt=_snapshot_text(cover_alt, 500),
                )
            )
    shipments: dict[UUID, Shipment] = {}
    if order_ids:
        shipments = {
            shipment.order_id: shipment
            for shipment in (
                await session.scalars(select(Shipment).where(Shipment.order_id.in_(order_ids)))
            ).all()
        }
    policy = None
    if any(shipments.values()):
        try:
            policy = await load_tracking_policy(session)
        except DomainError:
            policy = None
    orders: list[OrderSummary] = []
    for order in order_rows:
        shipment = shipments.get(order.id)
        tracking_url = None
        if shipment is not None and policy is not None:
            tracking_url = build_shipment_tracking_url(
                policy, shipment.carrier, shipment.tracking_number
            )
        ship_info = None
        if (
            order.shipping_data is not None
            or order.delivery_point_snapshot is not None
            or order.fulfillment_status in {"ready_for_pickup", "picked_up"}
        ):
            method = (order.shipping_data or {}).get("method")
            physical_items = [
                {
                    "product_id": str(item.product_id),
                    "name": item.name,
                    "quantity": item.quantity,
                    "cover_url": item.cover_url,
                    "cover_alt": item.cover_alt,
                }
                for item in items_by_order[order.id]
                if item.kind == "BOOK"
            ]
            link_status: Literal["available", "not_shipped", "unconfigured"] = (
                "available" if tracking_url else "unconfigured" if shipment else "not_shipped"
            )
            ship_info = ShipmentSummary(
                order_id=order.id,
                delivery_method=method,
                fulfillment_status=order.fulfillment_status,
                carrier=shipment.carrier if shipment else None,
                shipment_status=shipment.status if shipment else None,
                tracking_number=shipment.tracking_number if shipment else None,
                tracking_url=tracking_url,
                tracking_link_status=link_status,
                shipped_at=shipment.shipped_at if shipment else None,
                delivered_at=shipment.delivered_at if shipment else None,
                pickup_ready_at=order.pickup_ready_at,
                picked_up_at=order.picked_up_at,
                pickup_point=order.delivery_point_snapshot,
                shipping_address=(order.shipping_data or {}).get("address"),
                pickup_information=None,
                items=physical_items,
            )
        orders.append(
            OrderSummary(
                id=order.id,
                number=_order_number(order),
                created_at=order.created_at,
                status=order.status,
                buyer_email=order.email,
                fulfillment_status=order.fulfillment_status,
                amount_due_grosz=order.amount_due_grosz,
                paid_amount_grosz=order.amount_due_grosz if order.status == "paid" else None,
                calculation=order.calculation_snapshot,
                invoice=order.invoice_data,
                shipping=order.shipping_data,
                delivery_point=order.delivery_point_snapshot,
                items=items_by_order[order.id],
                shipment=ship_info,
                documents=[],
            )
        )
    return await _history_response(
        session, customer_id, response, page, page_size, orders, total, counts
    )


async def _history_response(
    session: AsyncSession,
    customer_id: UUID,
    response: Response,
    page: int,
    page_size: int,
    items: list[OrderSummary],
    total: int,
    counts: dict[str, int],
) -> OrderHistoryResponse:
    response.headers.update(PRIVATE_HEADERS)
    customer = await session.get(Customer, customer_id)
    help_setting = await session.scalar(
        select(AppSetting).where(AppSetting.key == "vouchers.public.v1")
    )
    help_value = help_setting.value if help_setting is not None else {}
    contact_email = (
        _snapshot_text(help_value.get("contact_email"), 320)
        if isinstance(help_value, dict)
        else None
    )
    contact_phone = (
        _snapshot_text(help_value.get("contact_phone"), 40)
        if isinstance(help_value, dict)
        else None
    )
    first_purchase = await session.scalar(
        select(func.min(Order.created_at)).where(
            Order.customer_id == customer_id, Order.status == "paid"
        )
    )
    return OrderHistoryResponse(
        customer_name=f"{customer.first_name} {customer.last_name}" if customer else "Klientka",
        contact_email=contact_email,
        contact_phone=contact_phone,
        first_purchase_at=first_purchase,
        total_count=total,
        counts=counts or {"all": 0, "in_progress": 0, "completed": 0, "invoices": 0},
        page=page,
        page_size=page_size,
        items=items,
    )
