"""Discount codes and information pages (owner-managed, staff read-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sensoria.modules.content.models import ContentPage, CookieConsent, FaqEntry
from sensoria.modules.orders.models import DiscountCode
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .common import Owner, Page, PageSize, SessionDependency, Staff
from .routes_products import ChapterBlock

router = APIRouter(tags=["admin-marketing"])


class DiscountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=3, max_length=100)
    type: str = Field(pattern="^(percentage|fixed_amount)$")
    value: StrictInt = Field(gt=0)
    min_order_value: StrictInt = Field(default=0, ge=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses: StrictInt | None = Field(default=None, gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def coherent(self) -> DiscountInput:
        if self.type == "percentage" and not 1 <= self.value <= 100:
            raise ValueError("Rabat procentowy musi mieścić się w zakresie 1–100.")
        for stamp in (self.valid_from, self.valid_to):
            if stamp is not None and stamp.tzinfo is None:
                raise ValueError("Daty muszą zawierać strefę czasową.")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("Koniec ważności musi być po początku.")
        return self


class DiscountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: StrictInt | None = Field(default=None, gt=0)
    min_order_value: StrictInt | None = Field(default=None, ge=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses: StrictInt | None = Field(default=None, gt=0)
    is_active: bool | None = None


class PageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=300)
    blocks: list[ChapterBlock] = Field(max_length=500)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return value.strip()


def _discount_view(code: DiscountCode) -> dict[str, Any]:
    return {
        "id": str(code.id),
        "code": code.code,
        "type": code.type,
        "value": code.value,
        "min_order_value": code.min_order_value,
        "valid_from": code.valid_from.isoformat() if code.valid_from else None,
        "valid_to": code.valid_to.isoformat() if code.valid_to else None,
        "max_uses": code.max_uses,
        "used_count": code.used_count,
        "is_active": code.is_active,
    }


@router.get("/discount-codes")
async def list_discounts(
    session: SessionDependency, _admin: Staff, page: Page = 1, page_size: PageSize = 50
) -> dict[str, Any]:
    total = int(await session.scalar(select(func.count()).select_from(DiscountCode)) or 0)
    rows = list(
        (
            await session.scalars(
                select(DiscountCode)
                .order_by(DiscountCode.created_at.desc(), DiscountCode.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()
    )
    return {"total": total, "items": [_discount_view(c) for c in rows]}


@router.post("/discount-codes", status_code=201)
async def create_discount(
    payload: DiscountInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    try:
        async with session.begin():
            code = DiscountCode(**payload.model_dump())
            session.add(code)
            await session.flush()
            session.add(
                AuditLog(
                    actor_type=ActorType.ADMINISTRATOR,
                    actor_id=admin.id,
                    entity_type="discount_code",
                    entity_id=code.id,
                    action="discount.created",
                    payload={"type": code.type},
                )
            )
            return _discount_view(code)
    except IntegrityError:
        raise DomainError("DISCOUNT_CODE_EXISTS", "Taki kod rabatowy już istnieje.", 409) from None


@router.patch("/discount-codes/{code_id}")
async def update_discount(
    code_id: UUID, payload: DiscountPatch, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    async with session.begin():
        code = await session.scalar(
            select(DiscountCode).where(DiscountCode.id == code_id).with_for_update()
        )
        if code is None:
            raise DomainError("DISCOUNT_NOT_FOUND", "Nie znaleziono kodu.", 404)
        for name in payload.model_fields_set:
            setattr(code, name, getattr(payload, name))
        if code.max_uses is not None and code.max_uses < code.used_count:
            raise DomainError(
                "DISCOUNT_MAX_USES_TOO_LOW", "Limit nie może być niższy niż liczba użyć.", 422
            )
        if code.valid_from and code.valid_to and code.valid_to <= code.valid_from:
            raise DomainError(
                "DISCOUNT_DATES_INVALID", "Koniec ważności musi być po początku.", 422
            )
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="discount_code",
                entity_id=code.id,
                action="discount.updated",
                payload={"fields": sorted(payload.model_fields_set)},
            )
        )
        await session.flush()
        return _discount_view(code)


@router.get("/pages")
async def list_pages(
    session: SessionDependency,
    _admin: Staff,
    status: Annotated[str | None, Query(pattern="^(draft|published)$")] = None,
) -> dict[str, Any]:
    statement = select(ContentPage).order_by(ContentPage.title)
    if status:
        statement = statement.where(ContentPage.status == status)
    rows = (await session.scalars(statement)).all()
    return {
        "items": [
            {"id": str(p.id), "slug": p.slug, "title": p.title, "status": p.status} for p in rows
        ]
    }


@router.get("/pages/{slug}")
async def get_page(slug: str, session: SessionDependency, _admin: Staff) -> dict[str, Any]:
    page = await session.scalar(select(ContentPage).where(ContentPage.slug == slug))
    if page is None:
        raise DomainError("PAGE_NOT_FOUND", "Nie znaleziono strony.", 404)
    return {
        "id": str(page.id),
        "slug": page.slug,
        "title": page.title,
        "summary": page.summary,
        "blocks": page.blocks,
        "status": page.status,
    }


@router.put("/pages/{slug}")
async def upsert_page(
    slug: str, payload: PageInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    if payload.slug != slug:
        raise DomainError("PAGE_SLUG_MISMATCH", "Adres strony musi zgadzać się z treścią.", 422)
    async with session.begin():
        page = await session.scalar(
            select(ContentPage).where(ContentPage.slug == slug).with_for_update()
        )
        blocks = [b.model_dump(exclude_none=True) for b in payload.blocks]
        if page is None:
            page = ContentPage(slug=slug, title=payload.title, blocks=blocks, status="draft")
            session.add(page)
        page.title, page.summary, page.blocks = payload.title, payload.summary, blocks
        page.updated_by = admin.id
        await session.flush()
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="content_page",
                entity_id=page.id,
                action="page.saved",
                payload={"slug": slug},
            )
        )
        return {"id": str(page.id), "slug": slug, "status": page.status}


@router.post("/pages/{slug}/publish")
async def publish_page(slug: str, session: SessionDependency, admin: Owner) -> dict[str, str]:
    async with session.begin():
        page = await session.scalar(
            select(ContentPage).where(ContentPage.slug == slug).with_for_update()
        )
        if page is None:
            raise DomainError("PAGE_NOT_FOUND", "Nie znaleziono strony.", 404)
        if not page.blocks:
            raise DomainError("PAGE_EMPTY", "Nie można opublikować pustej strony.", 422)
        page.status, page.published_at = "published", datetime.now(UTC)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="content_page",
                entity_id=page.id,
                action="page.published",
                payload={"slug": slug},
            )
        )
    return {"slug": slug, "status": "published"}


@router.post("/pages/{slug}/unpublish")
async def unpublish_page(slug: str, session: SessionDependency, admin: Owner) -> dict[str, str]:
    async with session.begin():
        page = await session.scalar(
            select(ContentPage).where(ContentPage.slug == slug).with_for_update()
        )
        if page is None:
            raise DomainError("PAGE_NOT_FOUND", "Nie znaleziono strony.", 404)
        page.status = "draft"
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="content_page",
                entity_id=page.id,
                action="page.unpublished",
                payload={"slug": slug},
            )
        )
    return {"slug": slug, "status": "draft"}


class FaqInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(min_length=1, max_length=60)
    question: str = Field(min_length=3, max_length=300)
    answer: str = Field(min_length=3, max_length=6000)
    position: int = Field(default=0, ge=0, le=10_000)
    published: bool = False


def _faq_view(e: FaqEntry) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "category": e.category,
        "question": e.question,
        "answer": e.answer,
        "position": e.position,
        "published": e.published,
    }


@router.get("/faq")
async def list_faq(session: SessionDependency, _admin: Staff) -> dict[str, Any]:
    rows = (
        await session.scalars(select(FaqEntry).order_by(FaqEntry.category, FaqEntry.position))
    ).all()
    return {"items": [_faq_view(e) for e in rows]}


@router.post("/faq", status_code=201)
async def create_faq(payload: FaqInput, session: SessionDependency, admin: Owner) -> dict[str, Any]:
    async with session.begin():
        entry = FaqEntry(**payload.model_dump())
        session.add(entry)
        await session.flush()
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="faq_entry",
                entity_id=entry.id,
                action="faq.created",
                payload={},
            )
        )
        return _faq_view(entry)


@router.put("/faq/{entry_id}")
async def update_faq(
    entry_id: UUID, payload: FaqInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    async with session.begin():
        entry = await session.scalar(
            select(FaqEntry).where(FaqEntry.id == entry_id).with_for_update()
        )
        if entry is None:
            raise DomainError("FAQ_NOT_FOUND", "Nie znaleziono pytania.", 404)
        for name, value in payload.model_dump().items():
            setattr(entry, name, value)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="faq_entry",
                entity_id=entry.id,
                action="faq.updated",
                payload={},
            )
        )
        await session.flush()
        return _faq_view(entry)


@router.delete("/faq/{entry_id}", status_code=204)
async def delete_faq(entry_id: UUID, session: SessionDependency, admin: Owner) -> None:
    async with session.begin():
        entry = await session.get(FaqEntry, entry_id)
        if entry is None:
            raise DomainError("FAQ_NOT_FOUND", "Nie znaleziono pytania.", 404)
        await session.delete(entry)
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="faq_entry",
                entity_id=entry_id,
                action="faq.deleted",
                payload={},
            )
        )


@router.get("/cookie-consents")
async def cookie_register(
    session: SessionDependency, _admin: Owner, page: Page = 1, page_size: PageSize = 50
) -> dict[str, Any]:
    total = int(await session.scalar(select(func.count()).select_from(CookieConsent)) or 0)
    rows = (
        await session.scalars(
            select(CookieConsent)
            .order_by(CookieConsent.created_at.desc(), CookieConsent.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {
        "total": total,
        "items": [
            {
                "subject_id": str(r.subject_id),
                "policy_version": r.policy_version,
                "analytics": r.analytics,
                "marketing": r.marketing,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/audit")
async def audit_log_view(
    session: SessionDependency,
    _admin: Owner,
    entity_type: Annotated[str | None, Query(max_length=100)] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, Any]:
    statement = select(AuditLog)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if action:
        statement = statement.where(AuditLog.action.like(f"{action}%"))
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await session.scalars(
            statement.order_by(AuditLog.created_at.desc(), AuditLog.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {
        "total": total,
        "items": [
            {
                "at": r.created_at.isoformat(),
                "actor_type": r.actor_type.value,
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id),
                "action": r.action,
                "payload": r.payload,
            }
            for r in rows
        ],
    }
