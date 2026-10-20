"""Public support endpoints (authorized by order token or the buyer's session)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.orders.models import Order
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.shared.errors import DomainError

from . import service
from .models import SupportCase

router = APIRouter(prefix="/support", tags=["support"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
OrderToken = Annotated[str | None, Query(min_length=16, max_length=128)]


class CaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    kind: str = Field(pattern="^(withdrawal|return|complaint)$")
    order_item_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


async def _order(
    session: AsyncSession, request: Request, order_id: UUID, order_token: str | None
) -> Order:
    order = await session.get(Order, order_id)
    missing = DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    if order_token is not None:
        if order is None or not verify_order_access_token(order_id, order_token):
            raise missing
        return order
    customer_id = await require_customer_id(request, session)
    if order is None or order.customer_id != customer_id:
        raise missing
    return order


@router.get("/orders/{order_id}")
async def order_support(
    order_id: UUID, request: Request, session: SessionDependency, order_token: OrderToken = None
) -> dict[str, Any]:
    order = await _order(session, request, order_id, order_token)
    from datetime import UTC, datetime

    window_end = await service.withdrawal_window_end(session, order)
    cases = list(
        (
            await session.scalars(
                select(SupportCase)
                .where(SupportCase.order_id == order.id)
                .order_by(SupportCase.created_at.desc())
            )
        ).all()
    )
    return {
        "order_number": order.public_number,
        "withdrawal_open": order.status == "paid" and datetime.now(UTC) <= window_end,
        "withdrawal_until": window_end.isoformat(),
        "cases": [
            {
                "number": c.public_number,
                "kind": c.kind,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
                "resolution_note": c.resolution_note,
            }
            for c in cases
        ],
    }


@router.post("/cases", status_code=201)
async def create_case(
    payload: CaseInput, request: Request, session: SessionDependency, order_token: OrderToken = None
) -> dict[str, Any]:
    order = await _order(session, request, payload.order_id, order_token)
    case = await service.create_case(
        session,
        order=order,
        kind=payload.kind,
        order_item_id=payload.order_item_id,
        message=payload.message,
    )
    await session.commit()
    return {"number": case.public_number, "status": case.status}
