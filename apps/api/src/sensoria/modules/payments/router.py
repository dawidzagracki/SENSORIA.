"""Payment endpoints: hosted session start, order status and the Stripe webhook."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.shared.rate_limit import enforce_rate_limit

from .schemas import OrderStatusResponse, PaymentSessionResponse
from .service import order_status_view, process_event, start_payment
from .stripe_client import verify_webhook

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/orders/{order_id}/session", response_model=PaymentSessionResponse)
async def create_payment_session(
    order_id: UUID,
    request: Request,
    session: SessionDependency,
    token: str = Query(min_length=16, max_length=128),
) -> PaymentSessionResponse:
    await enforce_rate_limit(session, request, scope="payment_session", limit=30, window_seconds=60)
    settings = get_settings()
    site_url = settings.SITE_URL or "http://localhost"
    payment = await start_payment(
        session, settings, order_id=order_id, token=token, site_url=site_url
    )
    assert payment.checkout_url is not None
    return PaymentSessionResponse(
        payment_id=payment.id,
        payment_url=payment.checkout_url,
        status=payment.status,
        attempt=payment.attempt,
    )


@router.get("/orders/{order_id}", response_model=OrderStatusResponse)
async def read_order_status(
    order_id: UUID,
    session: SessionDependency,
    token: str = Query(min_length=16, max_length=128),
) -> OrderStatusResponse:
    return OrderStatusResponse(**await order_status_view(session, order_id=order_id, token=token))


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    session: SessionDependency,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    payload = await request.body()
    event = verify_webhook(get_settings(), payload, stripe_signature)
    outcome = await process_event(session, event)
    return {"outcome": outcome}
