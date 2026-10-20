"""Protected administrative operations; every route needs an authenticated administrator."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.admin.auth import AdminPrincipal, require_admin_principal
from sensoria.modules.admin.routes_auth import router as auth_router
from sensoria.modules.admin.routes_customers import router as customers_router
from sensoria.modules.admin.routes_dashboard import router as dashboard_router
from sensoria.modules.admin.routes_orders import router as orders_router
from sensoria.modules.admin.routes_products import router as products_router
from sensoria.modules.admin.routes_vouchers import router as vouchers_router
from sensoria.modules.orders.shipments import (
    build_tracking_url,
    correct_shipment,
    load_tracking_policy,
    mark_picked_up,
    mark_pickup_ready,
    mark_shipment_delivered,
    ship_order,
    shipping_dashboard,
    validate_tracking_number,
)

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(customers_router)
router.include_router(vouchers_router)
router.include_router(products_router)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
AdminDependency = Annotated[AdminPrincipal, Depends(require_admin_principal)]


class ShipmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    carrier: str = Field(min_length=1, max_length=40)
    tracking_number: str = Field(min_length=1, max_length=160)


class ShipmentCorrectionInput(ShipmentInput):
    reason: str = Field(min_length=1, max_length=500)
    resend_notification: bool = False


class ShipmentResponse(BaseModel):
    shipment_id: UUID
    order_id: UUID
    carrier: str
    tracking_number: str
    shipped_at: datetime
    status: str
    tracking_url: str
    warning: str | None = None


class FulfillmentResponse(BaseModel):
    order_id: UUID
    fulfillment_status: str


@router.get("/orders/shipping-dashboard")
async def read_shipping_dashboard(
    session: SessionDependency, _admin: AdminDependency
) -> dict[str, object]:
    return await shipping_dashboard(session)


@router.post("/orders/{order_id}/ship", response_model=ShipmentResponse)
async def create_shipment(
    order_id: UUID,
    payload: ShipmentInput,
    session: SessionDependency,
    admin: AdminDependency,
) -> ShipmentResponse:
    shipment = await ship_order(
        session,
        order_id=order_id,
        carrier=payload.carrier,
        tracking_number=payload.tracking_number,
        actor_id=admin.id,
    )
    policy = await load_tracking_policy(session)
    number, warning = validate_tracking_number(shipment.tracking_number)
    return ShipmentResponse(
        shipment_id=shipment.id,
        order_id=order_id,
        carrier=shipment.carrier,
        tracking_number=number,
        shipped_at=shipment.shipped_at,
        status=shipment.status,
        tracking_url=build_tracking_url(policy, payload.carrier, number),
        warning=warning,
    )


@router.patch("/orders/{order_id}/shipment", response_model=ShipmentResponse)
async def update_shipment(
    order_id: UUID,
    payload: ShipmentCorrectionInput,
    session: SessionDependency,
    admin: AdminDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ShipmentResponse:
    shipment = await correct_shipment(
        session,
        order_id=order_id,
        carrier=payload.carrier,
        tracking_number=payload.tracking_number,
        actor_id=admin.id,
        reason=payload.reason,
        resend_notification=payload.resend_notification,
        operation_key=idempotency_key,
    )
    policy = await load_tracking_policy(session)
    number, warning = validate_tracking_number(shipment.tracking_number)
    carrier_key = payload.carrier
    return ShipmentResponse(
        shipment_id=shipment.id,
        order_id=order_id,
        carrier=shipment.carrier,
        tracking_number=number,
        shipped_at=shipment.shipped_at,
        status=shipment.status,
        tracking_url=build_tracking_url(policy, carrier_key, number),
        warning=warning,
    )


@router.post("/orders/{order_id}/delivered", response_model=FulfillmentResponse)
async def mark_delivered(
    order_id: UUID, session: SessionDependency, admin: AdminDependency
) -> FulfillmentResponse:
    await mark_shipment_delivered(session, order_id=order_id, actor_id=admin.id)
    return FulfillmentResponse(order_id=order_id, fulfillment_status="delivered")


@router.post("/orders/{order_id}/pickup-ready", response_model=FulfillmentResponse)
async def pickup_ready(
    order_id: UUID, session: SessionDependency, admin: AdminDependency
) -> FulfillmentResponse:
    order = await mark_pickup_ready(session, order_id=order_id, actor_id=admin.id)
    return FulfillmentResponse(order_id=order_id, fulfillment_status=order.fulfillment_status)


@router.post("/orders/{order_id}/picked-up", response_model=FulfillmentResponse)
async def picked_up(
    order_id: UUID, session: SessionDependency, admin: AdminDependency
) -> FulfillmentResponse:
    order = await mark_picked_up(session, order_id=order_id, actor_id=admin.id)
    return FulfillmentResponse(order_id=order_id, fulfillment_status=order.fulfillment_status)


# Included last so static paths such as /orders/shipping-dashboard win over /orders/{order_id}.
router.include_router(orders_router)
