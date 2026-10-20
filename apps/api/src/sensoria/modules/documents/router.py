"""Document endpoints for guest (order token) and logged-in buyers."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.documents.models import SalesDocument
from sensoria.modules.documents.service import document_pdf_path, issue_document_for_order
from sensoria.modules.library.streaming import file_response
from sensoria.modules.orders.models import Order
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.shared.errors import DomainError

router = APIRouter(prefix="/documents", tags=["documents"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
NOT_FOUND = DomainError("DOCUMENT_NOT_FOUND", "Nie znaleziono dokumentu.", 404)


class DocumentView(BaseModel):
    id: UUID
    kind: str
    number: str
    issued_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentView]


async def _authorized_order(
    session: AsyncSession, request: Request, order_id: UUID, order_token: str | None
) -> Order:
    order = await session.get(Order, order_id)
    if order_token is not None:
        if order is None or not verify_order_access_token(order_id, order_token):
            raise NOT_FOUND
        return order
    customer_id = await require_customer_id(request, session)
    if order is None or order.customer_id != customer_id:
        raise NOT_FOUND
    return order


@router.get("/orders/{order_id}", response_model=DocumentList)
async def list_documents(
    order_id: UUID,
    request: Request,
    session: SessionDependency,
    order_token: Annotated[str | None, Query(min_length=16, max_length=128)] = None,
) -> DocumentList:
    order = await _authorized_order(session, request, order_id, order_token)
    if order.status != "paid":
        return DocumentList(items=[])
    try:
        async with session.begin_nested():
            await issue_document_for_order(session, order.id)
    except DomainError as error:
        if error.code != "SELLER_NOT_CONFIGURED":
            raise
    await session.commit()
    rows = list(
        (
            await session.scalars(
                select(SalesDocument)
                .where(SalesDocument.order_id == order.id)
                .order_by(SalesDocument.issued_at)
            )
        ).all()
    )
    return DocumentList(
        items=[
            DocumentView(id=r.id, kind=r.kind, number=r.number, issued_at=r.issued_at) for r in rows
        ]
    )


@router.get("/{document_id}/pdf")
async def download_document(
    document_id: UUID,
    request: Request,
    session: SessionDependency,
    order_token: Annotated[str | None, Query(min_length=16, max_length=128)] = None,
) -> StreamingResponse:
    document = await session.get(SalesDocument, document_id)
    if document is None:
        raise NOT_FOUND
    await _authorized_order(session, request, document.order_id, order_token)
    path, name = await document_pdf_path(session, document)
    await session.commit()
    response, _ = file_response(
        path, media_type="application/pdf", filename=name, range_header=None
    )
    return response
