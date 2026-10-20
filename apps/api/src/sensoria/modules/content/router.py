"""Public read access to published information pages."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.shared.errors import DomainError

from .models import ContentPage

router = APIRouter(prefix="/pages", tags=["pages"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_pages(session: SessionDependency) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(ContentPage).where(ContentPage.status == "published").order_by(ContentPage.title)
        )
    ).all()
    return {"items": [{"slug": p.slug, "title": p.title, "summary": p.summary} for p in rows]}


@router.get("/{slug}")
async def read_page(slug: str, session: SessionDependency) -> dict[str, Any]:
    page = await session.scalar(
        select(ContentPage).where(ContentPage.slug == slug, ContentPage.status == "published")
    )
    if page is None:
        raise DomainError("PAGE_NOT_FOUND", "Nie znaleziono strony.", 404)
    return {
        "slug": page.slug,
        "title": page.title,
        "summary": page.summary,
        "blocks": page.blocks,
        "updated_at": page.updated_at.isoformat(),
    }
