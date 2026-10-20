"""Public, sample-only media access with shared PostgreSQL limits and counters."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import math
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import case, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sensoria.config import get_settings
from sensoria.database import get_session
from sensoria.shared.errors import DomainError

from .models import Product, SampleAccessSession, SampleRateWindow
from .sample_storage import (
    LocalSampleStorage,
    SampleContentType,
    SampleKind,
    SampleStorageError,
)
from .types import ProductKind, ProductStatus

router = APIRouter(prefix="/products/{slug}/sample", tags=["product-samples"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class SampleOpenResponse(BaseModel):
    """Opaque, short-lived playback URL and non-sensitive media metadata."""

    sample_url: str
    content_type: SampleContentType
    pages: int | None = None
    duration_seconds: int | None = None
    expires_in_seconds: int


def _secret() -> bytes:
    return get_settings().SECRET_KEY.get_secret_value().encode("utf-8")


def _storage() -> LocalSampleStorage:
    return LocalSampleStorage(get_settings().SAMPLE_STORAGE_ROOT)


def _client_ip(request: Request) -> str:
    """Trust forwarding headers only when the direct peer is in configured CIDRs."""

    peer = request.client.host if request.client is not None else "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return "unknown"
    settings = get_settings()
    trusted = []
    for item in settings.TRUSTED_PROXY_CIDRS.split(","):
        value = item.strip()
        if value:
            try:
                trusted.append(ipaddress.ip_network(value, strict=False))
            except ValueError:
                # Invalid proxy configuration never grants trust to a header.
                return str(peer_address)
    if not any(peer_address in network for network in trusted):
        return str(peer_address)

    forwarded = request.headers.get("x-forwarded-for", "")
    try:
        chain = [ipaddress.ip_address(part.strip()) for part in forwarded.split(",")]
    except ValueError:
        return str(peer_address)
    for address in reversed(chain):
        if not any(address in network for network in trusted):
            return str(address)
    return str(chain[0]) if chain else str(peer_address)


def _digest(value: str) -> str:
    return hmac.new(_secret(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _grant_for(row: SampleAccessSession) -> str:
    """Derive a retry-stable opaque grant; only its digest is stored in PostgreSQL."""

    message = f"{row.id}:{row.product_id}:{row.expires_at.isoformat()}".encode()
    return (
        base64.urlsafe_b64encode(hmac.new(_secret(), message, hashlib.sha256).digest())
        .decode("ascii")
        .rstrip("=")
    )


def _sample_details(product: Product) -> tuple[SampleKind, str, int | None, int | None] | None:
    if product.kind is ProductKind.DIGITAL and product.digital is not None:
        digital_sample = product.digital
        if (
            digital_sample.sample_enabled
            and digital_sample.sample_file_path
            and digital_sample.sample_pages
        ):
            return "pdf", digital_sample.sample_file_path, digital_sample.sample_pages, None
    if product.kind is ProductKind.AUDIOBOOK and product.audiobook is not None:
        audio_sample = product.audiobook
        if (
            audio_sample.sample_enabled
            and audio_sample.sample_file_path
            and audio_sample.sample_duration_seconds
        ):
            return (
                "audio",
                audio_sample.sample_file_path,
                None,
                audio_sample.sample_duration_seconds,
            )
    return None


async def _published_product(session: AsyncSession, slug: str) -> Product | None:
    result = await session.scalar(
        select(Product)
        .where(
            Product.slug == slug,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at.is_not(None),
            Product.published_at <= func.now(),
        )
        .options(selectinload(Product.digital), selectinload(Product.audiobook))
        .execution_options(populate_existing=True)
    )
    return result


def _not_available() -> DomainError:
    return DomainError("SAMPLE_NOT_AVAILABLE", "Darmowy fragment nie jest dostępny.", 404)


async def _consume_rate(
    session: AsyncSession,
    client_key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """Atomically consume one distributed PostgreSQL rate-window request."""

    # Bound storage growth for clients that do not return; keys contain only HMACs.
    await session.execute(
        delete(SampleRateWindow).where(
            SampleRateWindow.window_started_at < func.now() - text("interval '1 day'")
        )
    )
    expired_before = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, window_seconds)
    expired_window = SampleRateWindow.window_started_at <= expired_before
    rate_stmt = (
        insert(SampleRateWindow)
        .values(client_key=client_key, window_started_at=func.now(), request_count=1)
        .on_conflict_do_update(
            index_elements=[SampleRateWindow.client_key],
            set_={
                "window_started_at": case(
                    (expired_window, func.now()), else_=SampleRateWindow.window_started_at
                ),
                "request_count": case(
                    (expired_window, 1), else_=SampleRateWindow.request_count + 1
                ),
            },
        )
        .returning(
            SampleRateWindow.window_started_at,
            SampleRateWindow.request_count,
            func.now().label("database_now"),
        )
    )
    rate_row = (await session.execute(rate_stmt)).one()
    if rate_row.request_count > limit:
        retry_after = max(
            1,
            math.ceil(
                rate_row.window_started_at.timestamp()
                + window_seconds
                - rate_row.database_now.timestamp()
            ),
        )
        await session.commit()
        raise DomainError(
            "SAMPLE_RATE_LIMITED",
            "Limit żądań fragmentu został osiągnięty. Spróbuj ponownie później.",
            429,
            {"Retry-After": str(retry_after)},
        )


@router.post("/open", response_model=SampleOpenResponse)
async def open_sample(
    slug: str,
    request: Request,
    session: SessionDependency,
    open_id: Annotated[UUID, Header(alias="X-Sample-Open-Id")],
) -> SampleOpenResponse:
    """Count one intentional opening; retries with the same ID return one grant."""

    product = await _published_product(session, slug)
    if product is None:
        raise _not_available()
    details = _sample_details(product)
    if details is None:
        raise _not_available()
    kind, key, pages, duration = details
    storage = _storage()
    if not storage.exists(kind, key):
        raise _not_available()

    client_ip = _client_ip(request)
    client_key = _digest(client_ip)
    request_key = _digest(f"{client_key}:{open_id}")
    now = await session.scalar(select(func.now()))
    existing = await session.scalar(
        select(SampleAccessSession).where(
            SampleAccessSession.request_key == request_key,
            SampleAccessSession.product_id == product.id,
            SampleAccessSession.expires_at > now,
        )
    )
    if existing is not None:
        grant = _grant_for(existing)
        return SampleOpenResponse(
            sample_url=f"/products/{slug}/sample?grant={grant}",
            content_type=storage.content_type(kind),
            pages=pages,
            duration_seconds=duration,
            expires_in_seconds=get_settings().SAMPLE_SESSION_TTL_SECONDS,
        )

    settings = get_settings()
    await _consume_rate(
        session,
        _digest(f"open:{client_ip}"),
        limit=settings.SAMPLE_OPEN_LIMIT,
        window_seconds=settings.SAMPLE_OPEN_WINDOW_SECONDS,
    )

    await session.execute(
        delete(SampleAccessSession).where(SampleAccessSession.expires_at <= func.now())
    )
    session_id = uuid4()
    expires_at = func.now() + func.make_interval(
        0, 0, 0, 0, 0, 0, settings.SAMPLE_SESSION_TTL_SECONDS
    )
    placeholder_hash = hashlib.sha256(uuid4().bytes).hexdigest()
    inserted = await session.execute(
        insert(SampleAccessSession)
        .values(
            id=session_id,
            product_id=product.id,
            token_hash=placeholder_hash,
            request_key=request_key,
            expires_at=expires_at,
            request_count=0,
        )
        .on_conflict_do_nothing(index_elements=[SampleAccessSession.request_key])
        .returning(SampleAccessSession.id)
    )
    if inserted.scalar_one_or_none() is None:
        retry_row = await session.scalar(
            select(SampleAccessSession).where(SampleAccessSession.request_key == request_key)
        )
        if retry_row is None or retry_row.expires_at <= datetime.now(UTC):
            await session.rollback()
            raise DomainError("SAMPLE_OPEN_RETRY", "Nie można ponowić otwarcia próbki.", 409)
        await session.commit()
        grant = _grant_for(retry_row)
        return SampleOpenResponse(
            sample_url=f"/products/{slug}/sample?grant={grant}",
            content_type=storage.content_type(kind),
            pages=pages,
            duration_seconds=duration,
            expires_in_seconds=settings.SAMPLE_SESSION_TTL_SECONDS,
        )

    session_row = await session.get(SampleAccessSession, session_id)
    if session_row is None:
        raise RuntimeError("Sample access session failed to persist.")
    token = _grant_for(session_row)
    session_row.token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    counter = await session.execute(
        update(Product)
        .where(
            Product.id == product.id,
            Product.status == ProductStatus.PUBLISHED,
            Product.published_at <= func.now(),
        )
        .values(sample_open_count=Product.sample_open_count + 1)
        .returning(Product.id)
    )
    if counter.scalar_one_or_none() is None:
        await session.rollback()
        raise _not_available()
    await session.commit()
    return SampleOpenResponse(
        sample_url=f"/products/{slug}/sample?grant={token}",
        content_type=storage.content_type(kind),
        pages=pages,
        duration_seconds=duration,
        expires_in_seconds=settings.SAMPLE_SESSION_TTL_SECONDS,
    )


def _parse_range(value: str | None, size: int) -> tuple[int, int, bool]:
    if value is None:
        return 0, size - 1, False
    match = _RANGE.fullmatch(value.strip())
    if match is None or "," in value:
        raise DomainError(
            "SAMPLE_RANGE_INVALID",
            "Zakres próbki jest nieprawidłowy.",
            416,
            {"Content-Range": f"bytes */{size}"},
        )
    first, last = match.groups()
    if not first and not last:
        raise DomainError("SAMPLE_RANGE_INVALID", "Zakres próbki jest nieprawidłowy.", 416)
    if not first:
        suffix_length = int(last)
        if suffix_length <= 0:
            raise DomainError("SAMPLE_RANGE_INVALID", "Zakres próbki jest nieprawidłowy.", 416)
        start = max(0, size - suffix_length)
        end = size - 1
    else:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise DomainError(
            "SAMPLE_RANGE_INVALID",
            "Zakres próbki jest poza dostępnym plikiem.",
            416,
            {"Content-Range": f"bytes */{size}"},
        )
    return start, end, True


@router.get("")
async def read_sample(
    slug: str,
    request: Request,
    session: SessionDependency,
    grant: Annotated[str, Query(min_length=40, max_length=60)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """Stream only the sample named by the public product's own metadata."""

    product = await _published_product(session, slug)
    if product is None:
        raise _not_available()
    details = _sample_details(product)
    if details is None:
        raise _not_available()
    kind, key, _pages, _duration = details
    settings = get_settings()
    token_hash = hashlib.sha256(grant.encode("ascii", errors="ignore")).hexdigest()
    # Validate the short-lived, product-bound grant before opening any media file.
    access = await session.scalar(
        select(SampleAccessSession).where(
            SampleAccessSession.token_hash == token_hash,
            SampleAccessSession.product_id == product.id,
            SampleAccessSession.expires_at > func.now(),
            SampleAccessSession.request_count < settings.SAMPLE_SESSION_REQUEST_LIMIT,
        )
    )
    if access is None:
        raise _not_available()

    await _consume_rate(
        session,
        _digest(f"stream:{_client_ip(request)}"),
        limit=settings.SAMPLE_STREAM_LIMIT,
        window_seconds=settings.SAMPLE_STREAM_WINDOW_SECONDS,
    )

    storage = _storage()
    try:
        media, size = storage.open(kind, key)
    except SampleStorageError:
        raise _not_available() from None

    request_row = await session.execute(
        update(SampleAccessSession)
        .where(
            SampleAccessSession.token_hash == token_hash,
            SampleAccessSession.product_id == product.id,
            SampleAccessSession.expires_at > func.now(),
            SampleAccessSession.request_count < settings.SAMPLE_SESSION_REQUEST_LIMIT,
        )
        .values(request_count=SampleAccessSession.request_count + 1)
        .returning(SampleAccessSession.id)
    )
    if request_row.scalar_one_or_none() is None:
        media.close()
        raise DomainError(
            "SAMPLE_SESSION_LIMITED",
            "Sesja podglądu wygasła lub wykorzystała limit żądań.",
            429,
            {"Retry-After": "1"},
        )
    await session.commit()

    try:
        start, end, partial = _parse_range(range_header, size)
    except DomainError:
        media.close()
        raise
    content_length = end - start + 1
    media.seek(start)

    async def chunks() -> AsyncIterator[bytes]:
        remaining = content_length
        try:
            while remaining:
                block = media.read(min(64 * 1024, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block
        finally:
            media.close()

    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'inline; filename="sample.{"pdf" if kind == "pdf" else "mp3"}"',
        "Content-Length": str(content_length),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
    status_code = 200
    if partial:
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        chunks(),
        status_code=status_code,
        headers=headers,
        media_type=storage.content_type(kind),
    )
