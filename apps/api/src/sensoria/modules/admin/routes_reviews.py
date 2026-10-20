"""Review moderation queue."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from sensoria.modules.catalog.models import Product
from sensoria.modules.reviews import service
from sensoria.modules.reviews.models import Review

from .common import Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/reviews", tags=["admin-reviews"])


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    note: str | None = Field(default=None, max_length=500)


def _view(review: Review, product_name: str) -> dict[str, Any]:
    return {
        "id": str(review.id),
        "product": product_name,
        "product_id": str(review.product_id),
        "author": review.author_name,
        "rating": review.rating,
        "title": review.title,
        "body": review.body,
        "status": review.status,
        "created_at": review.created_at.isoformat(),
        "moderation_note": review.moderation_note,
    }


@router.get("")
async def queue(
    session: SessionDependency,
    _admin: Staff,
    status: Annotated[str, Query(pattern="^(pending|approved|rejected)$")] = "pending",
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    base = select(Review, Product.name).join(Product, Product.id == Review.product_id)
    base = base.where(Review.status == status)
    total = int(await session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = (
        await session.execute(
            base.order_by(Review.created_at.asc(), Review.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {"total": total, "items": [_view(r, name) for r, name in rows]}


@router.post("/{review_id}/decision")
async def decide(
    review_id: UUID, payload: DecisionInput, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        review = await service.decide(
            session, review_id, admin_id=admin.id, approve=payload.approve, note=payload.note
        )
        product = await session.get(Product, review.product_id)
        return _view(review, product.name if product else "")
