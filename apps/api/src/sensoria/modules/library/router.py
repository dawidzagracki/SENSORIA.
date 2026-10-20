"""Library endpoints: library listing, protected downloads, reader and audio streaming."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.accounts.auth import require_customer_id
from sensoria.modules.catalog.models import Product
from sensoria.modules.library import service
from sensoria.modules.library.models import EbookChapter, ProductFile
from sensoria.modules.library.schemas import (
    ChapterResponse,
    DownloadLinkRequest,
    DownloadLinkResponse,
    EntitlementDetail,
    LibraryResponse,
    ProgressInput,
)
from sensoria.modules.library.streaming import file_response
from sensoria.modules.orders.models import Order
from sensoria.modules.payments.tokens import verify_order_access_token
from sensoria.modules.storage.service import StorageService
from sensoria.shared.errors import DomainError

router = APIRouter(prefix="/library", tags=["library"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
OrderToken = Annotated[str | None, Query(alias="order_token", min_length=16, max_length=128)]
PRIVATE = {"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"}


@router.get("/mine", response_model=LibraryResponse)
async def my_library(request: Request, session: SessionDependency) -> LibraryResponse:
    customer_id = await require_customer_id(request, session)
    return LibraryResponse.model_validate(
        {"items": await service.customer_library(session, customer_id)}
    )


@router.get("/orders/{order_id}", response_model=LibraryResponse)
async def order_library(
    order_id: UUID, session: SessionDependency, order_token: Annotated[str, Query(min_length=16)]
) -> LibraryResponse:
    order = await session.get(Order, order_id)
    if order is None or not verify_order_access_token(order_id, order_token):
        raise DomainError("ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    if order.status != "paid":
        return LibraryResponse(items=[])
    return LibraryResponse.model_validate({"items": await service.order_library(session, order)})


@router.get("/entitlements/{entitlement_id}", response_model=EntitlementDetail)
async def entitlement_detail(
    entitlement_id: UUID,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
) -> EntitlementDetail:
    entitlement, order = await service.authorize_entitlement(
        session, request, entitlement_id, order_token
    )
    return EntitlementDetail.model_validate(
        await service.entitlement_detail(session, entitlement, order)
    )


@router.post("/entitlements/{entitlement_id}/download-links", response_model=DownloadLinkResponse)
async def create_download_link(
    entitlement_id: UUID,
    payload: DownloadLinkRequest,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
) -> DownloadLinkResponse:
    entitlement, _order = await service.authorize_entitlement(
        session, request, entitlement_id, order_token
    )
    token, link = await service.issue_download_link(session, entitlement, payload.file_id)
    await session.commit()
    return DownloadLinkResponse(
        url=f"/api/library/downloads/{token}",
        expires_at=link.expires_at,
        uses_left=link.max_uses - link.use_count,
    )


@router.get("/downloads/{token}")
async def download(
    token: str,
    session: SessionDependency,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    counts = range_header is None or range_header.strip().startswith("bytes=0-")
    entitlement, product_file = await service.redeem_download_link(
        session, token, counts_as_use=counts
    )
    stored, media_type, name = await service.prepare_file_for_entitlement(
        session, entitlement, product_file
    )
    await session.commit()
    path = StorageService().resolve_file(stored)
    response, _ = file_response(
        path, media_type=media_type, filename=name, range_header=range_header
    )
    return response


@router.get("/entitlements/{entitlement_id}/audio/{file_id}")
async def stream_audio(
    entitlement_id: UUID,
    file_id: UUID,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    entitlement, _order = await service.authorize_entitlement(
        session, request, entitlement_id, order_token
    )
    product_file = await session.get(ProductFile, file_id)
    if (
        product_file is None
        or product_file.product_id != entitlement.product_id
        or product_file.kind != "audio"
    ):
        raise DomainError("FILE_NOT_FOUND", "Nie znaleziono pliku.", 404)
    stored, media_type, name = await service.prepare_file_for_entitlement(
        session, entitlement, product_file
    )
    await session.commit()
    response, _ = file_response(
        StorageService().resolve_file(stored),
        media_type=media_type,
        filename=name,
        range_header=range_header,
        disposition="inline",
    )
    return response


@router.get("/entitlements/{entitlement_id}/chapters/{position}", response_model=ChapterResponse)
async def read_reader_chapter(
    entitlement_id: UUID,
    position: int,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
) -> ChapterResponse:
    entitlement, order = await service.authorize_entitlement(
        session, request, entitlement_id, order_token
    )
    chapter = await service.read_chapter(session, entitlement, position)
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(EbookChapter)
            .where(EbookChapter.product_id == entitlement.product_id)
        )
        or 0
    )
    product = await session.get(Product, entitlement.product_id)
    assert product is not None
    return ChapterResponse(
        position=chapter.position,
        title=chapter.title,
        blocks=chapter.blocks,
        total_chapters=total,
        footer=f"Egzemplarz dla: {order.email} · zamówienie {order.public_number}",
    )


@router.put("/entitlements/{entitlement_id}/progress", status_code=204)
async def put_progress(
    entitlement_id: UUID,
    payload: ProgressInput,
    request: Request,
    session: SessionDependency,
    order_token: OrderToken = None,
) -> None:
    entitlement, _order = await service.authorize_entitlement(
        session, request, entitlement_id, order_token
    )
    await service.save_progress(
        session,
        entitlement,
        position=payload.position,
        offset_seconds=payload.offset_seconds,
        completed_position=payload.completed_position,
        font_scale=payload.font_scale,
    )
    await session.commit()
