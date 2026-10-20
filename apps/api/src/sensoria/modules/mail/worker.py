"""Outbox worker: claim, send outside the transaction, record the outcome with backoff."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.storage.models import StoredFile
from sensoria.modules.storage.service import StorageService

from .bridge import SECRET_TEMPLATES
from .models import MailOutbox
from .transport import (
    MailTransport,
    OutgoingMail,
    PermanentMailError,
    SMTPTransport,
    TransientMailError,
    mail_configured,
    new_message_id,
)

logger = logging.getLogger("sensoria.mail")
MAX_ATTEMPTS = 6
BACKOFF = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=12),
)
STALE_LOCK = timedelta(minutes=15)


def _load_attachments(
    items: list[dict[str, object]], files: dict[str, StoredFile]
) -> list[tuple[str, bytes, str]]:
    storage = StorageService()
    loaded: list[tuple[str, bytes, str]] = []
    for item in items:
        stored = files.get(str(item["stored_file_id"]))
        if stored is None:
            raise PermanentMailError("attachment_missing")
        path = (
            storage.read_voucher_pdf(stored)
            if stored.category == "vouchers"
            else storage.resolve_file(stored)
        )
        loaded.append((str(item["name"]), path.read_bytes(), stored.mime_type))
    return loaded


async def process_outbox(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    transport: MailTransport | None = None,
    batch_size: int = 20,
    now: datetime | None = None,
) -> dict[str, int]:
    """Send due messages; returns counts. Without configuration nothing is claimed."""
    settings = get_settings()
    active = transport
    if active is None:
        if not mail_configured(settings):
            return {"sent": 0, "retry": 0, "failed": 0, "skipped_unconfigured": 1}
        active = SMTPTransport(settings)
    moment = now or datetime.now(UTC)
    counts = {"sent": 0, "retry": 0, "failed": 0, "skipped_unconfigured": 0}
    async with session_factory() as session, session.begin():
        rows = list(
            (
                await session.scalars(
                    select(MailOutbox)
                    .where(
                        or_(
                            MailOutbox.status.in_(("pending", "retry"))
                            & (MailOutbox.next_attempt_at <= func.now()),
                            (MailOutbox.status == "sending")
                            & (MailOutbox.locked_at <= moment - STALE_LOCK),
                        )
                    )
                    .order_by(MailOutbox.next_attempt_at, MailOutbox.id)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for row in rows:
            row.status = "sending"
            row.locked_at = moment
            row.attempts += 1
        claimed = [
            (
                row.id,
                OutgoingMail(
                    message_id=row.provider_message_id or new_message_id(),
                    to=row.recipient,
                    subject=row.subject,
                    html=row.html_body,
                    text=row.text_body,
                    attachments=[],
                ),
                row.attachments,
                row.attempts,
            )
            for row in rows
        ]
        file_ids = {str(a["stored_file_id"]) for _, _, atts, _ in claimed for a in atts}
        files = (
            {
                str(f.id): f
                for f in (
                    await session.scalars(
                        select(StoredFile).where(StoredFile.id.in_(list(file_ids)))
                    )
                ).all()
            }
            if file_ids
            else {}
        )
        for row in rows:
            row.provider_message_id = next(m.message_id for i, m, _, _ in claimed if i == row.id)
    outcomes: list[tuple[UUID, str, str | None, str | None]] = []
    for outbox_id, mail, attachments, attempts in claimed:
        try:
            loaded = _load_attachments(attachments, files)
            await active.send(
                OutgoingMail(mail.message_id, mail.to, mail.subject, mail.html, mail.text, loaded)
            )
            outcomes.append((outbox_id, "sent", mail.message_id, None))
        except PermanentMailError as error:
            outcomes.append((outbox_id, "failed", None, str(error)[:200]))
        except (TransientMailError, OSError) as error:
            code = str(error)[:200] or type(error).__name__
            status = "failed" if attempts >= MAX_ATTEMPTS else "retry"
            outcomes.append((outbox_id, status, None, code))
        except Exception as error:
            logger.error("Nieoczekiwany błąd wysyłki [%s].", type(error).__name__)
            status = "failed" if attempts >= MAX_ATTEMPTS else "retry"
            outcomes.append((outbox_id, status, None, type(error).__name__))
    async with session_factory() as session, session.begin():
        for outbox_id, status, message_id, error_code in outcomes:
            locked = await session.get(MailOutbox, outbox_id, with_for_update=True)
            if locked is None:
                continue
            row = locked
            row.status = status
            row.locked_at = None
            row.last_error = error_code
            if status == "sent":
                row.sent_at = moment
                row.provider_message_id = message_id
                if row.template_key in SECRET_TEMPLATES:
                    # Bearer links must not outlive delivery in the message log.
                    row.html_body = row.text_body = "[usunięto po wysyłce]"
            if status == "failed" and row.template_key in SECRET_TEMPLATES:
                row.html_body = row.text_body = "[usunięto po błędzie]"
            if status == "failed" and row.template_key != "ops_alert":
                from sensoria.modules.ops.alerts import describe, notify_owner

                await notify_owner(
                    session,
                    key=f"mail-failed:{row.id}",
                    title="Nie udało się wysłać wiadomości",
                    lines=describe(szablon=row.template_key, blad=error_code),
                )
            elif status == "retry":
                row.next_attempt_at = moment + BACKOFF[min(row.attempts, len(BACKOFF)) - 1]
            counts[status] += 1
    return counts


async def mail_scheduler() -> None:
    from .bridge import dispatch_legacy_jobs

    interval = get_settings().MAIL_WORKER_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval)
        try:
            await dispatch_legacy_jobs()
            await process_outbox()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Worker poczty zakończył się błędem [%s].", type(error).__name__)
