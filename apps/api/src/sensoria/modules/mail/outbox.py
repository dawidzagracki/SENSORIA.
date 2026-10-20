"""Transactional enqueueing; idempotent by key so retries never duplicate a message."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MailOutbox
from .templates import render_template


async def enqueue_mail(
    session: AsyncSession,
    *,
    template_key: str,
    recipient: str,
    variables: dict[str, Any],
    idempotency_key: str,
    attachments: list[dict[str, Any]] | None = None,
    order_id: UUID | None = None,
) -> MailOutbox:
    """Insert into the caller's transaction; returns the existing row on key reuse."""
    existing = await session.scalar(
        select(MailOutbox).where(MailOutbox.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    subject, html_body, text_body = render_template(template_key, variables)
    row = MailOutbox(
        idempotency_key=idempotency_key,
        template_key=template_key,
        recipient=recipient.strip(),
        subject=subject[:300],
        html_body=html_body,
        text_body=text_body,
        attachments=attachments or [],
        order_id=order_id,
    )
    session.add(row)
    await session.flush()
    return row
