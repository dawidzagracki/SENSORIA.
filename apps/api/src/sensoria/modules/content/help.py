"""Help center (FAQ with search) and the cookie consent register."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.shared.app_settings import AppSetting

from .models import CookieConsent, FaqEntry

router = APIRouter(tags=["help"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
COOKIE_POLICY_VERSION = "v1"


class CookieChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analytics: StrictBool = False
    marketing: StrictBool = False
    subject_id: UUID | None = None
    policy_version: str = Field(default=COOKIE_POLICY_VERSION, max_length=20)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/help")
async def help_center(
    session: SessionDependency, q: Annotated[str | None, Query(max_length=100)] = None
) -> dict[str, Any]:
    statement = select(FaqEntry).where(FaqEntry.published.is_(True))
    needle = q.strip() if q else ""
    if needle:
        pattern = f"%{_escape_like(needle.lower())}%"
        statement = statement.where(
            or_(
                func.lower(FaqEntry.question).like(pattern, escape="\\"),
                func.lower(FaqEntry.answer).like(pattern, escape="\\"),
            )
        )
    rows = list(
        (
            await session.scalars(
                statement.order_by(FaqEntry.category, FaqEntry.position, FaqEntry.id)
            )
        ).all()
    )
    if needle:  # questions that match the title come first
        rows.sort(key=lambda e: needle.lower() not in e.question.lower())
    contact = await session.scalar(select(AppSetting).where(AppSetting.key == "vouchers.public.v1"))
    contact_value = contact.value if contact and isinstance(contact.value, dict) else {}
    categories: dict[str, list[dict[str, str]]] = {}
    for entry in rows:
        categories.setdefault(entry.category, []).append(
            {"id": str(entry.id), "question": entry.question, "answer": entry.answer}
        )
    return {
        "query": needle,
        "total": len(rows),
        "categories": [{"name": name, "items": items} for name, items in categories.items()],
        "contact": {
            "email": contact_value.get("contact_email"),
            "phone": contact_value.get("contact_phone"),
        },
    }


@router.post("/consents/cookies", status_code=201)
async def record_cookie_consent(
    payload: CookieChoice, request: Request, session: SessionDependency
) -> dict[str, Any]:
    from sensoria.modules.accounts.privacy import hashed_client_ip

    subject = payload.subject_id or uuid4()
    row = CookieConsent(
        subject_id=subject,
        policy_version=payload.policy_version,
        analytics=payload.analytics,
        marketing=payload.marketing,
        ip_hash=hashed_client_ip(request),
    )
    session.add(row)
    await session.commit()
    return {
        "subject_id": str(subject),
        "policy_version": row.policy_version,
        "analytics": row.analytics,
        "marketing": row.marketing,
    }
