"""Hand durable intents from other modules to the outbox and reflect delivery back.

Every step is idempotent and bounded so concurrent workers and restarts are safe.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.accounts.mail_jobs import (
    build_auth_email_link,
    decrypt_auth_email_payload,
    email_change_job_is_current,
    login_link_job_is_current,
)
from sensoria.modules.accounts.models import AuthEmailJob
from sensoria.modules.orders.models import Order, OrderItem, Shipment, ShipmentNotificationJob
from sensoria.modules.orders.shipments import build_shipment_tracking_url, load_tracking_policy
from sensoria.modules.storage.service import StorageService
from sensoria.modules.vouchers.models import (
    Voucher,
    VoucherGiftDeliveryJob,
    VoucherReminder,
)
from sensoria.modules.vouchers.pdf_worker import render_voucher_pdf
from sensoria.modules.vouchers.service import (
    VOUCHER_TIMEZONE,
    confirm_gift_delivery_sent,
    voucher_valid_until_from_delivery,
)

from .models import MailOutbox
from .outbox import enqueue_mail

logger = logging.getLogger("sensoria.mail.bridge")
AUTH_TEMPLATE = {
    "password_reset": "password_reset",
    "email_verification": "email_verification",
    "login_link": "login_link",
    "email_change": "email_change",
}
SECRET_TEMPLATES = frozenset(AUTH_TEMPLATE.values())


class ReminderOutboxQueue:
    """VoucherReminderQueue adapter that writes to the outbox in the caller's transaction."""

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        reminder_id: Any,
        recipient_email: str,
        template_key: str,
        variables: dict[str, Any],
    ) -> str:
        row = await enqueue_mail(
            session,
            template_key=template_key,
            recipient=recipient_email,
            variables=variables,
            idempotency_key=f"reminder:{reminder_id}",
        )
        return str(row.id)


async def _auth_jobs(session: AsyncSession, limit: int) -> int:
    origin = get_settings().SITE_URL
    jobs = list(
        (
            await session.scalars(
                select(AuthEmailJob)
                .where(AuthEmailJob.status == "pending", AuthEmailJob.payload_ciphertext != "")
                .order_by(AuthEmailJob.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    handed = 0
    for job in jobs:
        if job.purpose not in AUTH_TEMPLATE:
            job.status = "failed"
            job.failure_code = "unknown_purpose"
            continue
        try:
            payload = decrypt_auth_email_payload(job.payload_ciphertext)
            token = payload["token"]
            if job.purpose == "login_link" and not await login_link_job_is_current(
                session, job.id, token
            ):
                job.status, job.failure_code = "cancelled", "link_superseded"
                continue
            if job.purpose == "email_change" and not await email_change_job_is_current(
                session, job.id, token
            ):
                job.status, job.failure_code = "cancelled", "link_superseded"
                continue
            link = build_auth_email_link(job.purpose, token, origin)
            await enqueue_mail(
                session,
                template_key=AUTH_TEMPLATE[job.purpose],
                recipient=payload["to"],
                variables={"link": link},
                idempotency_key=f"auth:{job.idempotency_key}",
            )
            job.status = "queued"
            job.queued_at = datetime.now(UTC)
            handed += 1
        except Exception as error:
            logger.error("Nie można przekazać wiadomości konta [%s].", type(error).__name__)
            job.status, job.failure_code = "failed", "handoff_error"
    return handed


async def _sync_auth_jobs(session: AsyncSession) -> None:
    jobs = list(
        (
            await session.scalars(
                select(AuthEmailJob).where(AuthEmailJob.status == "queued").limit(200)
            )
        ).all()
    )
    for job in jobs:
        row = await session.scalar(
            select(MailOutbox).where(MailOutbox.idempotency_key == f"auth:{job.idempotency_key}")
        )
        if row is None:
            continue
        if row.status == "sent":
            job.status, job.sent_at, job.payload_ciphertext = "sent", row.sent_at, ""
        elif row.status == "failed":
            job.status, job.failure_code, job.payload_ciphertext = "failed", "delivery_failed", ""


async def _shipment_jobs(session: AsyncSession, limit: int) -> int:
    jobs = list(
        (
            await session.scalars(
                select(ShipmentNotificationJob)
                .where(ShipmentNotificationJob.status == "pending")
                .order_by(ShipmentNotificationJob.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    handed = 0
    for job in jobs:
        order = await session.get(Order, job.order_id)
        if order is None:
            job.status, job.failure_code = "cancelled", "order_missing"
            continue
        variables: dict[str, Any] = {"order_number": order.public_number or str(order.id)}
        template = "pickup_ready"
        if job.kind in {"shipped", "manual_resend"}:
            shipment = await session.get(Shipment, job.shipment_id) if job.shipment_id else None
            if shipment is None:
                job.status, job.failure_code = "cancelled", "shipment_missing"
                continue
            template = "shipment_sent"
            tracking_url: str | None = None
            try:
                policy = await load_tracking_policy(session)
                tracking_url = build_shipment_tracking_url(
                    policy, shipment.carrier, shipment.tracking_number
                )
            except Exception:
                tracking_url = None
            variables.update(
                carrier=shipment.carrier,
                tracking_number=shipment.tracking_number,
                tracking_url=tracking_url,
            )
        await enqueue_mail(
            session,
            template_key=template,
            recipient=order.email,
            variables=variables,
            idempotency_key=f"shipment-job:{job.idempotency_key}",
            order_id=order.id,
        )
        job.status = "sending"
        job.queued_at = datetime.now(UTC)
        handed += 1
    return handed


async def _sync_shipment_jobs(session: AsyncSession) -> None:
    jobs = list(
        (
            await session.scalars(
                select(ShipmentNotificationJob)
                .where(ShipmentNotificationJob.status == "sending")
                .limit(200)
            )
        ).all()
    )
    for job in jobs:
        row = await session.scalar(
            select(MailOutbox).where(
                MailOutbox.idempotency_key == f"shipment-job:{job.idempotency_key}"
            )
        )
        if row is None:
            continue
        if row.status == "sent":
            job.status, job.sent_at = "sent", row.sent_at
        elif row.status == "failed":
            job.status, job.failed_at, job.failure_code = "failed", datetime.now(UTC), "delivery"


async def _voucher_deliveries(session: AsyncSession, limit: int) -> int:
    """Mail every rendered, non-gift voucher PDF to the buyer exactly once."""
    rows = (
        await session.execute(
            select(Voucher, Order)
            .join(OrderItem, OrderItem.id == Voucher.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.status == "paid",
                Voucher.gift_delivery_status == "not_gift",
                Voucher.pdf_file_id.is_not(None),
                Voucher.status == "active",
                ~select(MailOutbox.id)
                .where(MailOutbox.idempotency_key == func.concat("voucher-delivery:", Voucher.id))
                .exists(),
            )
            .order_by(Voucher.issued_at)
            .limit(limit)
        )
    ).all()
    origin = get_settings().SITE_URL or ""
    for voucher, order in rows:
        await enqueue_mail(
            session,
            template_key="voucher_delivery",
            recipient=order.email,
            variables={
                "service_name": voucher.issue_snapshot.get("service_name", "Voucher"),
                "code": voucher.code,
                "valid_until": voucher.valid_until.astimezone(VOUCHER_TIMEZONE).strftime(
                    "%d.%m.%Y"
                ),
                "voucher_url": f"{origin}/voucher/{voucher.code}",
            },
            idempotency_key=f"voucher-delivery:{voucher.id}",
            attachments=[{"stored_file_id": str(voucher.pdf_file_id), "name": "voucher.pdf"}],
            order_id=order.id,
        )
    return len(rows)


async def _gift_jobs(session: AsyncSession, limit: int, now: datetime) -> int:
    """Phase 1: render the gift PDF and enqueue the mail; validity starts at provider acceptance."""
    jobs = list(
        (
            await session.scalars(
                select(VoucherGiftDeliveryJob)
                .where(
                    VoucherGiftDeliveryJob.status.in_(("pending", "retry")),
                    VoucherGiftDeliveryJob.deliver_at <= now,
                )
                .order_by(VoucherGiftDeliveryJob.deliver_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    origin = get_settings().SITE_URL or "http://localhost"
    handed = 0
    for job in jobs:
        voucher = await session.get(Voucher, job.voucher_id)
        if (
            voucher is None
            or voucher.status == "cancelled"
            or voucher.gift_version != job.gift_version
        ):
            job.status = "cancelled"
            continue
        months = int(voucher.issue_snapshot["validity_months"])
        provisional = voucher_valid_until_from_delivery(now, months)
        content = await asyncio.to_thread(
            render_voucher_pdf, voucher, origin=origin, valid_until=provisional
        )
        async with session.begin_nested():
            stored = await StorageService().store_voucher_pdf(
                session, voucher_id=voucher.id, year=now.year, content=content
            )
        gift = voucher.issue_snapshot.get("gift") or {}
        order_id = await session.scalar(
            select(OrderItem.order_id).where(OrderItem.id == voucher.order_item_id)
        )
        await enqueue_mail(
            session,
            template_key="voucher_gift",
            recipient=job.recipient_email or voucher.recipient_email or "",
            variables={
                "recipient_name": gift.get("recipient_name") or "",
                "buyer_hint": "Bliska Ci osoba",
                "dedication": gift.get("dedication") or "",
                "service_name": voucher.issue_snapshot.get("service_name", "Voucher"),
                "code": voucher.code,
                "valid_until": provisional.astimezone(VOUCHER_TIMEZONE).strftime("%d.%m.%Y"),
            },
            idempotency_key=f"gift:{voucher.id}:{job.gift_version}",
            attachments=[{"stored_file_id": str(stored.id), "name": "voucher.pdf"}],
            order_id=order_id,
        )
        job.status = "queued"
        job.queue_message_id = f"gift:{voucher.id}:{job.gift_version}"
        handed += 1
    return handed


async def _sync_gift_jobs(session: AsyncSession) -> None:
    """Phase 2: after the provider accepted the message, fix validity from the real send time."""
    jobs = list(
        (
            await session.scalars(
                select(VoucherGiftDeliveryJob)
                .where(VoucherGiftDeliveryJob.status == "queued")
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for job in jobs:
        row = await session.scalar(
            select(MailOutbox).where(MailOutbox.idempotency_key == job.queue_message_id)
        )
        if row is None:
            continue
        if row.status == "sent" and row.sent_at is not None:
            job.provider_message_id = row.provider_message_id
            await confirm_gift_delivery_sent(
                session, job.voucher_id, sent_at=max(row.sent_at, job.deliver_at)
            )
        elif row.status == "failed":
            job.status, job.error_code = "blocked", "delivery_failed"


async def _sync_reminders(session: AsyncSession) -> None:
    reminders = list(
        (
            await session.scalars(
                select(VoucherReminder)
                .where(
                    VoucherReminder.status == "queued",
                    VoucherReminder.queue_message_id.is_not(None),
                )
                .limit(200)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for reminder in reminders:
        row = await session.scalar(
            select(MailOutbox).where(MailOutbox.idempotency_key == f"reminder:{reminder.id}")
        )
        if row is None:
            continue
        if row.status == "sent":
            reminder.status = "sent"
            reminder.sent_at = reminder.provider_accepted_at = row.sent_at
            reminder.provider_message_id = row.provider_message_id
        elif row.status == "failed":
            reminder.status, reminder.error_code = "failed", "delivery_failed"


async def dispatch_legacy_jobs(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, int]:
    moment = now or datetime.now(UTC)
    async with session_factory() as session, session.begin():
        counts = {
            "auth": await _auth_jobs(session, limit),
            "shipments": await _shipment_jobs(session, limit),
            "vouchers": await _voucher_deliveries(session, limit),
            "gifts": await _gift_jobs(session, limit, moment),
        }
        await _sync_auth_jobs(session)
        await _sync_shipment_jobs(session)
        await _sync_gift_jobs(session)
        await _sync_reminders(session)
    return counts
