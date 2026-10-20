"""Voucher expiry reminder qualification and queue integration contracts.

This module never sends mail. A queue adapter must insert into the project's durable
outbox in the same database transaction passed to it.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Date, and_, case, cast, exists, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.config import get_settings
from sensoria.database import SessionFactory
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog

from .models import Voucher, VoucherReminder, VoucherReminderRun
from .service import VOUCHER_TIMEZONE, days_until_expiry, effective_voucher_status

REMINDER_SETTINGS_KEY = "vouchers.reminders.v1"
DEFAULT_REMINDER_SETTINGS: dict[str, Any] = {
    "threshold_days": [30, 7],
    "local_time": "09:00",
    "timezone": "Europe/Warsaw",
    "max_messages_per_run": 200,
}
MAX_THRESHOLD_DAYS = 365
MAX_MESSAGES_PER_RUN = 5000


class VoucherReminderConfigurationError(ValueError):
    """Invalid operator-controlled reminder settings."""


class VoucherReminderConsentReader(Protocol):
    """[60] contract. None means the consent cannot be reliably established."""

    async def has_current_consent(
        self, session: AsyncSession, *, order_id: Any, email: str
    ) -> bool | None: ...


class VoucherReminderQueue(Protocol):
    """[62]/[63] contract; implementation must enqueue transactionally and idempotently."""

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        reminder_id: Any,
        recipient_email: str,
        template_key: str,
        variables: dict[str, Any],
    ) -> str: ...


@dataclass(frozen=True)
class ReminderSettings:
    threshold_days: tuple[int, ...]
    local_time: time
    timezone: ZoneInfo
    max_messages_per_run: int

    def as_json(self) -> dict[str, Any]:
        return {
            "threshold_days": list(self.threshold_days),
            "local_time": self.local_time.strftime("%H:%M"),
            "timezone": self.timezone.key,
            "max_messages_per_run": self.max_messages_per_run,
        }


def validate_reminder_settings(value: Any) -> ReminderSettings:
    """Parse app_settings strictly so bad values never silently disable safeguards."""
    if not isinstance(value, dict):
        raise VoucherReminderConfigurationError("Ustawienia przypomnień muszą być obiektem JSON.")
    thresholds = value.get("threshold_days")
    if (
        not isinstance(thresholds, list)
        or not thresholds
        or any(isinstance(day, bool) or not isinstance(day, int) for day in thresholds)
        or any(day < 1 or day > MAX_THRESHOLD_DAYS for day in thresholds)
        or thresholds != sorted(set(thresholds), reverse=True)
    ):
        raise VoucherReminderConfigurationError(
            "Progi przypomnień muszą być dodatnie, unikalne i malejące."
        )
    raw_time = value.get("local_time")
    if not isinstance(raw_time, str) or re.fullmatch(r"\d{2}:\d{2}", raw_time) is None:
        raise VoucherReminderConfigurationError("Godzina przypomnienia jest nieprawidłowa.")
    try:
        parsed_time = time.fromisoformat(raw_time)
    except ValueError:
        raise VoucherReminderConfigurationError(
            "Godzina przypomnienia jest nieprawidłowa."
        ) from None
    if parsed_time.tzinfo is not None or parsed_time.second or parsed_time.microsecond:
        raise VoucherReminderConfigurationError("Godzina musi mieć format HH:MM.")
    zone_name = value.get("timezone")
    if zone_name != "Europe/Warsaw":
        raise VoucherReminderConfigurationError("Strefa przypomnień musi być Europe/Warsaw.")
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, TypeError):
        raise VoucherReminderConfigurationError("Strefa przypomnień jest nieprawidłowa.") from None
    limit = value.get("max_messages_per_run")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_MESSAGES_PER_RUN
    ):
        raise VoucherReminderConfigurationError("Limit wiadomości na przebieg jest nieprawidłowy.")
    return ReminderSettings(tuple(thresholds), parsed_time, zone, limit)


async def load_reminder_settings(session: AsyncSession) -> ReminderSettings:
    value = await session.scalar(
        select(AppSetting.value).where(AppSetting.key == REMINDER_SETTINGS_KEY)
    )
    if value is None:
        return validate_reminder_settings(DEFAULT_REMINDER_SETTINGS)
    return validate_reminder_settings(value)


def next_local_run(now: datetime, settings: ReminderSettings) -> datetime:
    """Next fixed local wall-clock occurrence, converted to UTC across DST changes."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Wymagana jest strefowa data.")
    local_now = now.astimezone(settings.timezone)
    candidate = _valid_local_time(local_now.date(), settings)
    if candidate <= local_now:
        candidate = _valid_local_time(local_now.date() + timedelta(days=1), settings)
    return candidate.astimezone(UTC)


def _valid_local_time(day: date, settings: ReminderSettings) -> datetime:
    """Resolve a wall-clock time through DST gaps; ambiguous times use the first fold."""
    naive = datetime.combine(day, settings.local_time)
    for minute_offset in range(181):
        candidate = (naive + timedelta(minutes=minute_offset)).replace(
            tzinfo=settings.timezone, fold=0
        )
        if candidate.astimezone(UTC).astimezone(settings.timezone).replace(tzinfo=None) == (
            naive + timedelta(minutes=minute_offset)
        ):
            return candidate
    raise VoucherReminderConfigurationError("Nie można wyznaczyć lokalnej godziny zadania.")


def due_threshold(remaining_days: int, thresholds: tuple[int, ...]) -> int | None:
    """Select only the most current milestone; obsolete earlier milestones are skipped."""
    eligible = [threshold for threshold in thresholds if remaining_days <= threshold]
    return min(eligible) if eligible else None


def build_reminder_variables(voucher: Voucher, *, now: datetime, site_url: str) -> dict[str, Any]:
    """Build mail variables from trusted voucher snapshots and the configured origin."""
    local_expiry = voucher.valid_until.astimezone(VOUCHER_TIMEZONE).date()
    return {
        "service_name": str(
            voucher.issue_snapshot.get("service_name")
            or voucher.issue_snapshot.get("product_name")
            or "voucher"
        ),
        "code": voucher.code,
        "valid_until": local_expiry.strftime("%d.%m.%Y"),
        "days_remaining": max(0, days_until_expiry(voucher.valid_until, now=now)),
        "account_url": f"{site_url.rstrip('/')}/konto/vouchery",
        "extension_information": (
            "Jeśli nie zdążysz umówić wizyty, skontaktuj się z nami — porozmawiamy o przedłużeniu."
        ),
    }


async def _get_existing_reminder(
    session: AsyncSession, voucher_id: Any, cycle: datetime, threshold: int
) -> VoucherReminder | None:
    result = await session.scalar(
        select(VoucherReminder)
        .where(
            VoucherReminder.voucher_id == voucher_id,
            VoucherReminder.valid_until_snapshot == cycle,
            VoucherReminder.threshold_days == threshold,
        )
        .with_for_update()
    )
    return result


async def _upsert_reminder(
    session: AsyncSession,
    *,
    voucher: Voucher,
    threshold: int,
    status: str,
    skip_reason: str | None,
) -> VoucherReminder:
    existing = await _get_existing_reminder(session, voucher.id, voucher.valid_until, threshold)
    if existing is None:
        existing = VoucherReminder(
            voucher_id=voucher.id,
            valid_until_snapshot=voucher.valid_until,
            threshold_days=threshold,
            status=status,
            skip_reason=skip_reason,
        )
        session.add(existing)
    elif existing.status not in {"queued", "sent", "cancelled"}:
        existing.status = status
        existing.skip_reason = skip_reason
        existing.error_code = None
    await session.flush()
    return existing


async def _order_identity(session: AsyncSession, voucher: Voucher) -> tuple[Any, str]:
    row = await session.execute(
        select(Order.id, Order.email)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(OrderItem.id == voucher.order_item_id)
    )
    found = row.one_or_none()
    if found is None:
        raise LookupError("voucher_order_missing")
    return found.id, found.email.strip().casefold()


async def run_voucher_reminders(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    *,
    consent_reader: VoucherReminderConsentReader | None = None,
    queue: VoucherReminderQueue | None = None,
    now: datetime | None = None,
    site_url: str | None = None,
) -> dict[str, int | bool | str]:
    """Qualify a bounded daily batch. It never sends mail or infers consent."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    app_settings = get_settings()
    origin = site_url or app_settings.SITE_URL
    async with session_factory() as session:
        config = await load_reminder_settings(session)
    run = VoucherReminderRun(started_at=current, configuration=config.as_json())
    async with session_factory.begin() as session:
        session.add(run)
        await session.flush()
        run_id = run.id

    counts = {"checked": 0, "qualified": 0, "queued": 0, "skipped": 0, "errors": 0}
    skip_reasons: dict[str, int] = {}
    error_reasons: dict[str, int] = {}

    def record_reason(target: dict[str, int], reason: str) -> None:
        target[reason] = target.get(reason, 0) + 1

    has_more = False
    limit_reached = False
    try:
        async with session_factory() as session:
            max_days = config.threshold_days[0]
            local_now = current.astimezone(config.timezone).date()
            remaining_days_sql = (
                cast(func.timezone("Europe/Warsaw", Voucher.valid_until), Date) - local_now
            )
            target_threshold_sql = case(
                *[
                    (remaining_days_sql <= threshold, threshold)
                    for threshold in reversed(config.threshold_days)
                ],
                else_=None,
            )
            prior_delivery = exists(
                select(VoucherReminder.id).where(
                    VoucherReminder.voucher_id == Voucher.id,
                    VoucherReminder.valid_until_snapshot == Voucher.valid_until,
                    VoucherReminder.threshold_days == target_threshold_sql,
                    (
                        VoucherReminder.status.in_(["queued", "sent", "skipped", "cancelled"])
                        | and_(
                            VoucherReminder.status == "blocked",
                            VoucherReminder.retry_after.is_not(None),
                            VoucherReminder.retry_after > current,
                        )
                    ),
                )
            )
            candidates = list(
                (
                    await session.scalars(
                        select(Voucher)
                        .where(
                            Voucher.status == "active",
                            Voucher.redeemed_at.is_(None),
                            Voucher.valid_until > current,
                            remaining_days_sql >= 0,
                            remaining_days_sql <= max_days,
                            not_(prior_delivery),
                        )
                        .order_by(Voucher.valid_until, Voucher.id)
                        .limit(config.max_messages_per_run + 1)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
        has_more = len(candidates) > config.max_messages_per_run
        candidates = candidates[: config.max_messages_per_run]
        limit_reached = has_more
        for voucher in candidates:
            counts["checked"] += 1
            remaining = days_until_expiry(voucher.valid_until, now=current)
            threshold = due_threshold(remaining, config.threshold_days)
            if threshold is None or effective_voucher_status(voucher, now=current) in {
                "expired",
                "redeemed",
                "cancelled",
            }:
                counts["skipped"] += 1
                record_reason(skip_reasons, "no_longer_eligible")
                continue
            async with session_factory.begin() as item_session:
                locked = await item_session.scalar(
                    select(Voucher).where(Voucher.id == voucher.id).with_for_update()
                )
                if locked is None:
                    counts["skipped"] += 1
                    record_reason(skip_reasons, "voucher_missing")
                    continue
                locked_remaining = days_until_expiry(locked.valid_until, now=current)
                locked_threshold = due_threshold(locked_remaining, config.threshold_days)
                if (
                    locked.status != "active"
                    or locked.redeemed_at is not None
                    or locked.valid_until <= current
                    or locked_threshold is None
                    or effective_voucher_status(locked, now=current)
                    in {"expired", "redeemed", "cancelled"}
                ):
                    counts["skipped"] += 1
                    record_reason(skip_reasons, "voucher_no_longer_eligible")
                    continue
                threshold = locked_threshold
                counts["qualified"] += 1
                # An extension starts a new cycle. Unsent milestones from the old cycle
                # are cancelled, so their stale content can never reach a worker.
                old_rows = await item_session.scalars(
                    select(VoucherReminder)
                    .where(
                        VoucherReminder.voucher_id == locked.id,
                        VoucherReminder.valid_until_snapshot != locked.valid_until,
                        VoucherReminder.status.in_(["blocked", "skipped", "failed", "queued"]),
                    )
                    .with_for_update()
                )
                for old_row in old_rows:
                    old_row.status = "cancelled"
                    old_row.skip_reason = "validity_cycle_changed"
                for old_threshold in config.threshold_days:
                    if old_threshold > threshold:
                        prior = await _get_existing_reminder(
                            item_session, locked.id, locked.valid_until, old_threshold
                        )
                        if prior is None:
                            item_session.add(
                                VoucherReminder(
                                    voucher_id=locked.id,
                                    valid_until_snapshot=locked.valid_until,
                                    threshold_days=old_threshold,
                                    status="skipped",
                                    scheduled_at=current,
                                    skip_reason="superseded_by_later_threshold",
                                )
                            )
                        elif prior.status in {"blocked", "skipped", "failed"}:
                            prior.status = "skipped"
                            prior.skip_reason = "superseded_by_later_threshold"
                        elif prior.status == "queued":
                            prior.status = "cancelled"
                            prior.skip_reason = "superseded_by_later_threshold"
                reminder = await _upsert_reminder(
                    item_session,
                    voucher=locked,
                    threshold=threshold,
                    status="blocked",
                    skip_reason=None,
                )
                reminder.scheduled_at = current
                if reminder.status in {"queued", "sent", "cancelled"}:
                    continue
                if consent_reader is None:
                    reminder.skip_reason = "consent_integration_unavailable"
                    reminder.status = "blocked"
                    reminder.retry_after = current + timedelta(days=1)
                    counts["skipped"] += 1
                    record_reason(skip_reasons, "consent_integration_unavailable")
                    continue
                order_id, email = await _order_identity(item_session, locked)
                try:
                    consent = await consent_reader.has_current_consent(
                        item_session, order_id=order_id, email=email
                    )
                except Exception:
                    consent = None
                if consent is not True:
                    reminder.status = "skipped" if consent is False else "blocked"
                    reminder.skip_reason = (
                        "consent_not_granted" if consent is False else "consent_cannot_be_verified"
                    )
                    reminder.retry_after = None if consent is False else current + timedelta(days=1)
                    counts["skipped"] += 1
                    record_reason(
                        skip_reasons,
                        "consent_not_granted" if consent is False else "consent_cannot_be_verified",
                    )
                    continue
                if queue is None or origin is None:
                    reminder.status = "blocked"
                    reminder.skip_reason = (
                        "message_queue_unavailable"
                        if queue is None
                        else "public_origin_unconfigured"
                    )
                    reminder.retry_after = current + timedelta(days=1)
                    counts["skipped"] += 1
                    record_reason(
                        skip_reasons,
                        "message_queue_unavailable"
                        if queue is None
                        else "public_origin_unconfigured",
                    )
                    continue
                try:
                    async with item_session.begin_nested():
                        queue_id = await queue.enqueue(
                            item_session,
                            reminder_id=reminder.id,
                            recipient_email=email,
                            template_key="voucher_expiry_reminder",
                            variables=build_reminder_variables(
                                locked, now=current, site_url=origin
                            ),
                        )
                    if not queue_id.strip() or len(queue_id) > 200:
                        raise ValueError("Nieprawidłowy identyfikator wiadomości kolejki.")
                    reminder.status = "queued"
                    reminder.queue_message_id = queue_id
                    reminder.queued_at = current
                    reminder.skip_reason = None
                    reminder.retry_after = None
                    counts["queued"] += 1
                except Exception:
                    reminder.status = "blocked"
                    reminder.skip_reason = "message_queue_unavailable"
                    reminder.retry_after = current + timedelta(days=1)
                    counts["errors"] += 1
                    record_reason(error_reasons, "message_queue_unavailable")
        async with session_factory.begin() as end_session:
            run_row = await end_session.get(VoucherReminderRun, run_id)
            if run_row is not None:
                run_row.finished_at = datetime.now(UTC)
                run_row.checked_count = counts["checked"]
                run_row.qualified_count = counts["qualified"]
                run_row.queued_count = counts["queued"]
                run_row.skipped_count = counts["skipped"]
                run_row.error_count = counts["errors"]
                run_row.skip_reasons = skip_reasons
                run_row.error_reasons = error_reasons
                run_row.limit_reached = limit_reached
                run_row.has_more = has_more
                end_session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        actor_id=None,
                        entity_type="voucher_reminder_run",
                        entity_id=run_id,
                        action="completed",
                        payload={
                            "counts": counts,
                            "skip_reasons": skip_reasons,
                            "error_reasons": error_reasons,
                            "limit_reached": limit_reached,
                            "has_more": has_more,
                        },
                    )
                )
    except Exception:
        async with session_factory.begin() as end_session:
            run_row = await end_session.get(VoucherReminderRun, run_id)
            if run_row is not None:
                run_row.finished_at = datetime.now(UTC)
                run_row.error_count += 1
                error_reasons["batch_failed"] = error_reasons.get("batch_failed", 0) + 1
                run_row.skip_reasons = skip_reasons
                run_row.error_reasons = error_reasons
                end_session.add(
                    AuditLog(
                        actor_type=ActorType.SYSTEM,
                        actor_id=None,
                        entity_type="voucher_reminder_run",
                        entity_id=run_id,
                        action="failed",
                        payload={
                            "counts": counts,
                            "skip_reasons": skip_reasons,
                            "error_reasons": error_reasons,
                            "error": "batch_failed",
                        },
                    )
                )
        raise
    return {**counts, "limit_reached": limit_reached, "has_more": has_more, "run_id": str(run_id)}


async def revalidate_reminder_before_send(
    session: AsyncSession,
    reminder_id: Any,
    *,
    consent_reader: VoucherReminderConsentReader,
    now: datetime | None = None,
) -> bool:
    """[63] worker hook: cancel stale/withdrawn reminders immediately before delivery."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    reminder = await session.scalar(
        select(VoucherReminder).where(VoucherReminder.id == reminder_id).with_for_update()
    )
    if reminder is None or reminder.status != "queued":
        return False
    voucher = await session.scalar(
        select(Voucher).where(Voucher.id == reminder.voucher_id).with_for_update()
    )
    if (
        voucher is None
        or voucher.valid_until != reminder.valid_until_snapshot
        or effective_voucher_status(voucher, now=current) in {"expired", "redeemed", "cancelled"}
    ):
        reminder.status = "cancelled"
        reminder.skip_reason = "voucher_no_longer_eligible"
        return False
    order_id, email = await _order_identity(session, voucher)
    try:
        consent = await consent_reader.has_current_consent(session, order_id=order_id, email=email)
    except Exception:
        consent = None
    if consent is not True:
        reminder.status = "cancelled"
        reminder.skip_reason = "consent_withdrawn_or_unverifiable"
        return False
    remaining = days_until_expiry(voucher.valid_until, now=current)
    config = await load_reminder_settings(session)
    if due_threshold(remaining, config.threshold_days) != reminder.threshold_days:
        reminder.status = "cancelled"
        reminder.skip_reason = "threshold_no_longer_current"
        return False
    return True


async def mark_reminder_provider_accepted(
    session: AsyncSession,
    reminder_id: Any,
    *,
    provider_message_id: str,
    accepted_at: datetime | None = None,
) -> None:
    """Record provider acceptance only after the delivery worker confirms it."""
    reminder = await session.scalar(
        select(VoucherReminder).where(VoucherReminder.id == reminder_id).with_for_update()
    )
    if reminder is None or reminder.status not in {"queued", "sent"}:
        raise ValueError("Przypomnienie nie jest gotowe do potwierdzenia wysyłki.")
    if reminder.status != "sent":
        reminder.status = "sent"
        reminder.sent_at = (accepted_at or datetime.now(UTC)).astimezone(UTC)
        reminder.provider_accepted_at = reminder.sent_at
    reminder.provider_message_id = provider_message_id[:200]
    reminder.retry_after = None


async def mark_reminder_delivered(
    session: AsyncSession,
    reminder_id: Any,
    *,
    delivered_at: datetime | None = None,
) -> None:
    """Record mailbox delivery only when the configured provider reports it."""
    reminder = await session.scalar(
        select(VoucherReminder).where(VoucherReminder.id == reminder_id).with_for_update()
    )
    if reminder is None or reminder.status != "sent":
        raise ValueError("Wiadomość nie została potwierdzona przez dostawcę.")
    if reminder.delivered_at is None:
        reminder.delivered_at = (delivered_at or datetime.now(UTC)).astimezone(UTC)


async def mark_reminder_failed(
    session: AsyncSession,
    reminder_id: Any,
    *,
    error_code: str,
) -> None:
    """Store a bounded error code, never provider response text."""
    reminder = await session.scalar(
        select(VoucherReminder).where(VoucherReminder.id == reminder_id).with_for_update()
    )
    if reminder is None or reminder.status in {"sent", "cancelled"}:
        raise ValueError("Nie można oznaczyć tego przypomnienia jako błędnego.")
    if not re.fullmatch(r"[a-z0-9_]{1,80}", error_code):
        raise ValueError("Kod błędu przypomnienia jest nieprawidłowy.")
    reminder.status = "failed"
    reminder.error_code = error_code


async def voucher_reminder_scheduler() -> None:
    """Daily local-time scheduler; durable voucher locks deduplicate API workers."""
    from sensoria.modules.vouchers.reminder_integrations import (
        configured_queue,
        configured_reminder_consent_reader,
    )

    while True:
        try:
            async with SessionFactory() as session:
                config = await load_reminder_settings(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            import logging

            logging.getLogger("sensoria.vouchers.reminders").error(
                "Nie udało się odczytać ustawień przypomnień."
            )
            await asyncio.sleep(300)
            continue
        current = datetime.now(UTC)
        wake_at = next_local_run(current, config)
        await asyncio.sleep(max(1.0, (wake_at - current).total_seconds()))
        try:
            await run_voucher_reminders(
                consent_reader=configured_reminder_consent_reader(),
                queue=configured_queue(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never log voucher codes, email addresses or database exception text.
            import logging

            logging.getLogger("sensoria.vouchers.reminders").error(
                "Przebieg przypomnień voucherowych nie powiódł się."
            )
