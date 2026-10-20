"""Support case queue for staff."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from sensoria.modules.orders.models import Order
from sensoria.modules.support.models import SupportCase
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .common import Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/support-cases", tags=["admin-support"])


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(in_progress|resolved|rejected)$")
    resolution_note: str | None = Field(default=None, max_length=3000)


def _view(case: SupportCase, order_number: str | None) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "number": case.public_number,
        "kind": case.kind,
        "status": case.status,
        "email": case.email,
        "order_id": str(case.order_id),
        "order_number": order_number,
        "message": case.message,
        "resolution_note": case.resolution_note,
        "created_at": case.created_at.isoformat(),
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
    }


@router.get("")
async def list_cases(
    session: SessionDependency,
    _admin: Staff,
    status: Annotated[str | None, Query(pattern="^(new|in_progress|resolved|rejected)$")] = None,
    kind: Annotated[str | None, Query(pattern="^(withdrawal|return|complaint)$")] = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    base = select(SupportCase, Order.public_number).join(Order, Order.id == SupportCase.order_id)
    if status:
        base = base.where(SupportCase.status == status)
    if kind:
        base = base.where(SupportCase.kind == kind)
    total = int(await session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = (
        await session.execute(
            base.order_by(SupportCase.created_at.desc(), SupportCase.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {"total": total, "items": [_view(c, n) for c, n in rows]}


@router.patch("/{case_id}")
async def update_case(
    case_id: UUID, payload: CaseUpdate, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        case = await session.scalar(
            select(SupportCase).where(SupportCase.id == case_id).with_for_update()
        )
        if case is None:
            raise DomainError("CASE_NOT_FOUND", "Nie znaleziono zgłoszenia.", 404)
        if (
            payload.status in {"resolved", "rejected"}
            and not (payload.resolution_note or "").strip()
        ):
            raise DomainError("CASE_NOTE_REQUIRED", "Podaj uzasadnienie decyzji.", 422)
        case.status = payload.status
        case.resolution_note = payload.resolution_note
        case.handled_by = admin.id
        case.resolved_at = datetime.now(UTC) if payload.status != "in_progress" else None
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="support_case",
                entity_id=case.id,
                action=f"support.{payload.status}",
                payload={},
            )
        )
        await session.flush()
        number = await session.scalar(select(Order.public_number).where(Order.id == case.order_id))
        return _view(case, number)
