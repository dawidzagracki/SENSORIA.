"""Database-backed health endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.shared.errors import DomainError
from sensoria.shared.schemas import HealthResponse
from sensoria.version import APP_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(session: SessionDependency) -> HealthResponse:
    """Return ready only after PostgreSQL successfully executes SELECT 1."""

    try:
        result = await session.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise SQLAlchemyError("Health query returned an unexpected result")
    except (SQLAlchemyError, TimeoutError, OSError) as error:
        logger.warning("Database health query failed")
        raise DomainError(
            code="DATABASE_UNAVAILABLE",
            message="Baza danych jest chwilowo niedostępna.",
            status_code=503,
        ) from error

    return HealthResponse(status="ok", version=APP_VERSION, database="ok")


@router.get("/health/deep", tags=["health"])
async def deep_health(session: SessionDependency) -> dict[str, object]:
    """Operational probe: database, mail backlog, payment webhooks and PDF jobs.

    Returns 503 when something needs attention so an uptime monitor can alert on it.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from sensoria.modules.mail.models import MailOutbox
    from sensoria.modules.payments.models import PaymentEvent
    from sensoria.modules.vouchers.models import VoucherPDFJob

    now = datetime.now(UTC)
    try:
        await session.execute(text("SELECT 1"))
        stale_mail = int(
            await session.scalar(
                select(func.count())
                .select_from(MailOutbox)
                .where(
                    MailOutbox.status.in_(("pending", "retry")),
                    MailOutbox.next_attempt_at < now - timedelta(minutes=30),
                )
            )
            or 0
        )
        failed_mail = int(
            await session.scalar(
                select(func.count()).select_from(MailOutbox).where(MailOutbox.status == "failed")
            )
            or 0
        )
        stuck_pdf = int(
            await session.scalar(
                select(func.count())
                .select_from(VoucherPDFJob)
                .where(
                    VoucherPDFJob.status.in_(("pending", "processing")),
                    VoucherPDFJob.available_at < now - timedelta(minutes=30),
                )
            )
            or 0
        )
        last_webhook = await session.scalar(select(func.max(PaymentEvent.received_at)))
    except (SQLAlchemyError, TimeoutError, OSError) as error:
        raise DomainError(
            code="DATABASE_UNAVAILABLE",
            message="Baza danych jest chwilowo niedostępna.",
            status_code=503,
        ) from error
    problems = [
        name
        for name, bad in (
            ("mail_backlog", stale_mail > 0),
            ("mail_failed", failed_mail > 0),
            ("pdf_jobs_stuck", stuck_pdf > 0),
        )
        if bad
    ]
    body: dict[str, object] = {
        "status": "degraded" if problems else "ok",
        "problems": problems,
        "mail": {"stale": stale_mail, "failed": failed_mail},
        "voucher_pdf_stuck": stuck_pdf,
        "last_payment_event_at": last_webhook.isoformat() if last_webhook else None,
    }
    if problems:
        raise DomainError(
            code="HEALTH_DEGRADED",
            message="Wykryto problemy operacyjne: " + ", ".join(problems),
            status_code=503,
        )
    return body
