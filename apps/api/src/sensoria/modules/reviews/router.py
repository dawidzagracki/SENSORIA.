"""Public review endpoints: product reviews, eligibility and submission."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.accounts.models import Customer
from sensoria.modules.catalog.models import Product
from sensoria.modules.catalog.types import ProductStatus
from sensoria.modules.orders.models import Order
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.shared.errors import DomainError

from . import service
from .models import Review

router = APIRouter(prefix="/reviews", tags=["reviews"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
OrderToken = Annotated[str | None, Query(min_length=16, max_length=128)]
NO_STORE = {"Cache-Control": "private, no-store"}


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    order_item_id: UUID
    rating: StrictInt = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


async def _authorize(
    session: AsyncSession, request: Request, order_id: UUID, order_token: str | None
) -> tuple[Order, Customer | None]:
    """Order token (guest/email link) or the logged-in owner; never reveals other orders."""
    order = await session.get(Order, order_id)
    not_found = DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404, NO_STORE)
    if order_token is not None:
        if order is None or not verify_order_access_token(order_id, order_token):
            raise not_found
        customer = await session.get(Customer, order.customer_id) if order.customer_id else None
        return order, customer
    customer_id = await require_customer_id(request, session)
    if order is None or order.customer_id != customer_id:
        raise not_found
    return order, await session.get(Customer, customer_id)


@router.get("/products/{slug}")
async def product_reviews(
    slug: str,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    product = await session.scalar(
        select(Product).where(Product.slug == slug, Product.status == ProductStatus.PUBLISHED)
    )
    if product is None:
        raise DomainError("PRODUCT_NOT_FOUND", "Nie znaleziono produktu.", 404)
    summary = await service.product_summary(session, product.id)
    rows = list(
        (
            await session.scalars(
                select(Review)
                .where(Review.product_id == product.id, Review.status == "approved")
                .order_by(Review.created_at.desc(), Review.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
    )
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(Review)
            .where(Review.product_id == product.id, Review.status == "approved")
        )
        or 0
    )
    return {
        "summary": summary,
        "total": total,
        "items": [
            {
                "id": str(r.id),
                "author": r.author_name,
                "rating": r.rating,
                "title": r.title,
                "body": r.body,
                "created_at": r.created_at.isoformat(),
                "verified_purchase": True,
            }
            for r in rows
        ],
    }


@router.get("/eligible")
async def eligible(
    order_id: UUID, request: Request, session: SessionDependency, order_token: OrderToken = None
) -> dict[str, Any]:
    order, _customer = await _authorize(session, request, order_id, order_token)
    return {"items": await service.eligible_items(session, order)}


@router.post("", status_code=201)
async def create_review(
    payload: ReviewInput,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
) -> dict[str, Any]:
    order, customer = await _authorize(session, request, payload.order_id, order_token)
    review = await service.submit_review(
        session,
        order=order,
        order_item_id=payload.order_item_id,
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
        customer=customer,
    )
    await session.commit()
    return {
        "id": str(review.id),
        "status": review.status,
        "message": "Dziękujemy! Opinia pojawi się po moderacji.",
    }
