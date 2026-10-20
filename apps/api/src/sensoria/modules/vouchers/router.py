"""Public voucher verification and guest access to purchased vouchers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.privacy import hashed_client_ip
from sensoria.modules.library.streaming import file_response
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.modules.storage.models import StoredFile
from sensoria.modules.storage.service import StorageService
from sensoria.shared.errors import DomainError

from .models import Voucher, VoucherVerificationWindow
from .service import effective_voucher_status, verification_payload

router = APIRouter(prefix="/vouchers", tags=["vouchers"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CODE_RE = re.compile(r"^[A-Z0-9-]{4,13}$")
VERIFY_LIMIT_PER_MINUTE = 20
NO_STORE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}


async def _throttle(session: AsyncSession, request: Request) -> None:
    subject = hashed_client_ip(request) or "unknown"
    window = datetime.now(UTC).replace(second=0, microsecond=0)
    row = await session.scalar(
        pg_insert(VoucherVerificationWindow)
        .values(subject_hash=subject, window_started_at=window, request_count=1)
        .on_conflict_do_update(
            index_elements=["subject_hash", "window_started_at"],
            set_={"request_count": VoucherVerificationWindow.request_count + 1},
        )
        .returning(VoucherVerificationWindow.request_count)
    )
    if (row or 0) > VERIFY_LIMIT_PER_MINUTE:
        await session.commit()
        raise DomainError(
            "VOUCHER_VERIFY_RATE_LIMITED",
            "Zbyt wiele sprawdzeń. Spróbuj ponownie za chwilę.",
            429,
            {"Retry-After": "60", **NO_STORE},
        )


@router.get("/verify/{code}")
async def verify_voucher(code: str, request: Request, session: SessionDependency) -> dict[str, Any]:
    """Anonymous status check by code; reveals only status and expiry date, never buyer data."""
    normalized = code.strip().upper()
    await _throttle(session, request)
    voucher = (
        await session.scalar(select(Voucher).where(Voucher.code == normalized))
        if CODE_RE.fullmatch(normalized)
        else None
    )
    await session.commit()
    if voucher is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404, NO_STORE)
    return {**verification_payload(voucher), "code": voucher.code}


async def _order_for_token(session: AsyncSession, order_id: UUID, token: str) -> Order:
    order = await session.get(Order, order_id)
    if order is None or not verify_order_access_token(order_id, token):
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    return order


@router.get("/orders/{order_id}")
async def order_vouchers(
    order_id: UUID, session: SessionDependency, order_token: Annotated[str, Query(min_length=16)]
) -> dict[str, Any]:
    order = await _order_for_token(session, order_id, order_token)
    if order.status != "paid":
        return {"items": []}
    rows = list(
        (
            await session.scalars(
                select(Voucher)
                .join(OrderItem, OrderItem.id == Voucher.order_item_id)
                .where(OrderItem.order_id == order_id)
                .order_by(Voucher.issued_at, Voucher.unit_index)
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": str(v.id),
                "code": v.code,
                "service_name": v.issue_snapshot.get("service_name"),
                "status": effective_voucher_status(v),
                "valid_until": v.valid_until.isoformat(),
                "pdf_ready": v.pdf_file_id is not None,
                "is_gift": v.gift_delivery_status != "not_gift",
            }
            for v in rows
        ]
    }


@router.get("/{voucher_id}/pdf")
async def guest_voucher_pdf(
    voucher_id: UUID,
    session: SessionDependency,
    order_token: Annotated[str, Query(min_length=16)],
) -> StreamingResponse:
    voucher = await session.get(Voucher, voucher_id)
    item = await session.get(OrderItem, voucher.order_item_id) if voucher else None
    if voucher is None or item is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404)
    await _order_for_token(session, item.order_id, order_token)
    if effective_voucher_status(voucher) not in {"active", "expiring_soon"}:
        raise DomainError("VOUCHER_PDF_NOT_AVAILABLE", "Ten voucher nie jest już aktywny.", 409)
    if voucher.pdf_file_id is None:
        raise DomainError("VOUCHER_PDF_PREPARING", "Dokument vouchera jest przygotowywany.", 409)
    stored = await session.get(StoredFile, voucher.pdf_file_id)
    if stored is None or stored.scope_id != voucher.id:
        raise DomainError("VOUCHER_PDF_UNAVAILABLE", "Dokument vouchera jest niedostępny.", 404)
    path = StorageService().read_voucher_pdf(stored)
    response, _ = file_response(
        path, media_type="application/pdf", filename="voucher.pdf", range_header=None
    )
    return response
