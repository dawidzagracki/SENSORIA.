"""Voucher search, redemption, cancellation, extension and the event ledger."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select

from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.vouchers import admin_service
from sensoria.modules.vouchers.models import Voucher, VoucherEvent, VoucherExtensionRequest
from sensoria.modules.vouchers.service import effective_voucher_status
from sensoria.shared.errors import DomainError

from .common import Owner, Page, PageSize, SessionDependency, Staff

router = APIRouter(prefix="/vouchers", tags=["admin-vouchers"])


class RedeemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    performed_by: str = Field(min_length=2, max_length=200)
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class ReasonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)


class ExtendInput(ReasonInput):
    new_last_day: date


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    new_last_day: date | None = None
    note: str = Field(default="", max_length=2000)


def _view(voucher: Voucher, order: Order) -> dict[str, Any]:
    gift = voucher.issue_snapshot.get("gift") or {}
    return {
        "id": str(voucher.id),
        "code": voucher.code,
        "service_name": voucher.issue_snapshot.get("service_name"),
        "status": effective_voucher_status(voucher),
        "stored_status": voucher.status,
        "issued_at": voucher.issued_at.isoformat(),
        "valid_until": voucher.valid_until.isoformat(),
        "redeemed_at": voucher.redeemed_at.isoformat() if voucher.redeemed_at else None,
        "redeemed_by": voucher.redeemed_by,
        "buyer_email": order.email,
        "order_id": str(order.id),
        "order_number": order.public_number,
        "recipient_name": gift.get("recipient_name"),
        "recipient_email": voucher.recipient_email,
        "is_gift": voucher.gift_delivery_status != "not_gift",
    }


async def _joined(session: SessionDependency, voucher_id: UUID) -> tuple[Voucher, Order]:
    row = (
        await session.execute(
            select(Voucher, Order)
            .join(OrderItem, OrderItem.id == Voucher.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Voucher.id == voucher_id)
        )
    ).one_or_none()
    if row is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404)
    return row[0], row[1]


@router.get("")
async def search_vouchers(
    session: SessionDependency,
    _admin: Staff,
    q: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(active|redeemed|expired|cancelled)$"),
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict[str, Any]:
    statement = (
        select(Voucher, Order)
        .join(OrderItem, OrderItem.id == Voucher.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
    )
    if q:
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Voucher.code).like(needle),
                func.lower(Order.email).like(needle),
                func.lower(func.coalesce(Voucher.recipient_email, "")).like(needle),
                func.lower(func.coalesce(Voucher.recipient_name, "")).like(needle),
                func.lower(func.coalesce(Order.public_number, "")).like(needle),
            )
        )
    if status == "active":
        statement = statement.where(Voucher.status == "active", Voucher.valid_until > func.now())
    elif status == "expired":
        statement = statement.where(Voucher.status == "active", Voucher.valid_until <= func.now())
    elif status:
        statement = statement.where(Voucher.status == status)
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await session.execute(
            statement.order_by(Voucher.issued_at.desc(), Voucher.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {"total": total, "page": page, "items": [_view(v, o) for v, o in rows]}


@router.get("/events")
async def ledger(
    session: SessionDependency,
    _admin: Staff,
    action: str | None = Query(default=None, max_length=24),
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, Any]:
    statement = select(VoucherEvent, Voucher.code).join(
        Voucher, Voucher.id == VoucherEvent.voucher_id
    )
    if action:
        statement = statement.where(VoucherEvent.action == action)
    total = int(await session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await session.execute(
            statement.order_by(VoucherEvent.occurred_at.desc(), VoucherEvent.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(e.id),
                "voucher_id": str(e.voucher_id),
                "code": code,
                "action": e.action,
                "performed_by": e.performed_by,
                "admin_id": str(e.admin_id) if e.admin_id else None,
                "occurred_at": e.occurred_at.isoformat(),
                "previous_valid_until": e.previous_valid_until.isoformat()
                if e.previous_valid_until
                else None,
                "new_valid_until": e.new_valid_until.isoformat() if e.new_valid_until else None,
                "note": e.note,
            }
            for e, code in rows
        ],
    }


@router.get("/extension-requests")
async def extension_requests(
    session: SessionDependency, _admin: Staff, status: str = Query(default="pending")
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(VoucherExtensionRequest, Voucher.code)
            .join(Voucher, Voucher.id == VoucherExtensionRequest.voucher_id)
            .where(VoucherExtensionRequest.status == status)
            .order_by(VoucherExtensionRequest.created_at)
            .limit(200)
        )
    ).all()
    return {
        "items": [
            {
                "id": str(r.id),
                "voucher_id": str(r.voucher_id),
                "code": code,
                "message": r.message,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r, code in rows
        ]
    }


@router.post("/extension-requests/{request_id}/decision")
async def decide(
    request_id: UUID, payload: DecisionInput, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        record = await admin_service.decide_extension_request(
            session,
            request_id,
            admin_id=admin.id,
            approve=payload.approve,
            new_last_day=payload.new_last_day,
            note=payload.note or ("Zatwierdzono" if payload.approve else "Odrzucono"),
        )
    return {"id": str(record.id), "status": record.status}


@router.get("/{voucher_id}")
async def voucher_detail(
    voucher_id: UUID, session: SessionDependency, _admin: Staff
) -> dict[str, Any]:
    voucher, order = await _joined(session, voucher_id)
    events = list(
        (
            await session.scalars(
                select(VoucherEvent)
                .where(VoucherEvent.voucher_id == voucher_id)
                .order_by(VoucherEvent.occurred_at, VoucherEvent.created_at)
            )
        ).all()
    )
    return {
        **_view(voucher, order),
        "events": [
            {
                "action": e.action,
                "occurred_at": e.occurred_at.isoformat(),
                "performed_by": e.performed_by,
                "note": e.note,
                "new_valid_until": e.new_valid_until.isoformat() if e.new_valid_until else None,
            }
            for e in events
        ],
    }


@router.post("/{voucher_id}/redeem")
async def redeem_voucher(
    voucher_id: UUID, payload: RedeemInput, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        await admin_service.redeem(
            session,
            voucher_id,
            admin_id=admin.id,
            performed_by=payload.performed_by,
            occurred_at=payload.occurred_at,
            note=payload.note,
        )
    voucher, order = await _joined(session, voucher_id)
    return _view(voucher, order)


@router.post("/{voucher_id}/revert-redemption")
async def revert(
    voucher_id: UUID, payload: ReasonInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    async with session.begin():
        await admin_service.revert_redemption(
            session, voucher_id, admin_id=admin.id, reason=payload.reason
        )
    voucher, order = await _joined(session, voucher_id)
    return _view(voucher, order)


@router.post("/{voucher_id}/cancel")
async def cancel_voucher(
    voucher_id: UUID, payload: ReasonInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    async with session.begin():
        await admin_service.cancel(session, voucher_id, admin_id=admin.id, reason=payload.reason)
    voucher, order = await _joined(session, voucher_id)
    return _view(voucher, order)


@router.post("/{voucher_id}/extend")
async def extend_voucher(
    voucher_id: UUID, payload: ExtendInput, session: SessionDependency, admin: Staff
) -> dict[str, Any]:
    async with session.begin():
        await admin_service.extend(
            session,
            voucher_id,
            admin_id=admin.id,
            new_last_day=payload.new_last_day,
            reason=payload.reason,
        )
    voucher, order = await _joined(session, voucher_id)
    return _view(voucher, order)
