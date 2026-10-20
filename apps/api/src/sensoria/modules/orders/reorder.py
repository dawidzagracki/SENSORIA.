"""Authenticated reorder endpoints sharing the durable cart implementation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.shared.errors import DomainError

from .router import _set_cart_cookie
from .service import (
    preview_reorder_order,
    preview_reorder_voucher,
    reorder_order,
    reorder_voucher,
)

router = APIRouter(prefix="/orders", tags=["order-reorder"])
cart_reorder_router = APIRouter(prefix="/cart/reorder", tags=["order-reorder"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CustomerDependency = Annotated[UUID, Depends(require_customer_id)]


@cart_reorder_router.get("/orders/{order_id}/preview")
async def preview_customer_order_reorder(
    order_id: UUID,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, object]:
    result = await preview_reorder_order(
        session, customer_id=customer_id, order_id=order_id, cart_token=cart_token
    )
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return result


@cart_reorder_router.get("/vouchers/{voucher_id}/preview")
async def preview_customer_voucher_reorder(
    voucher_id: UUID,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, object]:
    result = await preview_reorder_voucher(
        session, customer_id=customer_id, voucher_id=voucher_id, cart_token=cart_token
    )
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return result


@router.post("/{order_id}/reorder")
async def reorder_customer_order(
    order_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> dict[str, object]:
    """Re-add live eligible lines to the shopper's existing opaque cart."""
    return await _reorder_order(
        order_id, request, response, session, customer_id, cart_token, idempotency_key
    )


@cart_reorder_router.post("/orders/{order_id}")
async def reorder_customer_order_from_cart_path(
    order_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> dict[str, object]:
    """Same operation under the cart-cookie path so HttpOnly scope stays narrow."""
    return await _reorder_order(
        order_id, request, response, session, customer_id, cart_token, idempotency_key
    )


async def _reorder_order(
    order_id: UUID,
    request: Request,
    response: Response,
    session: AsyncSession,
    customer_id: UUID,
    cart_token: str | None,
    idempotency_key: str,
) -> dict[str, object]:
    from sensoria.modules.accounts.router import _require_csrf

    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    await session.commit()
    cart, token, report = await reorder_order(
        session,
        customer_id=customer_id,
        order_id=order_id,
        cart_token=cart_token,
        idempotency_key=idempotency_key,
    )
    if cart.expires_at is None:
        raise DomainError("CART_EXPIRY_INVALID", "Nie można zapisać czasu ważności koszyka.", 500)
    _set_cart_cookie(response, token, cart.expires_at)
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {"report": report, "redirect": "/koszyk"}


@cart_reorder_router.post("/vouchers/{voucher_id}")
async def reorder_customer_voucher_from_cart_path(
    voucher_id: UUID,
    request: Request,
    response: Response,
    session: SessionDependency,
    customer_id: CustomerDependency,
    cart_token: Annotated[str | None, Cookie()] = None,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> dict[str, object]:
    """Voucher counterpart kept below the narrow cart-cookie path."""
    from sensoria.modules.accounts.router import _require_csrf

    await _require_csrf(request, session, request.headers.get("x-csrf-token"))
    await session.commit()
    cart, token, report = await reorder_voucher(
        session,
        customer_id=customer_id,
        voucher_id=voucher_id,
        cart_token=cart_token,
        idempotency_key=idempotency_key,
    )
    if cart.expires_at is None:
        raise DomainError("CART_EXPIRY_INVALID", "Nie można zapisać czasu ważności koszyka.", 500)
    _set_cart_cookie(response, token, cart.expires_at)
    response.headers.update(
        {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}
    )
    return {"report": report, "redirect": "/koszyk"}
