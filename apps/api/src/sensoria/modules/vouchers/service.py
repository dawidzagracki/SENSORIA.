"""Transactional voucher issuance, validity rules and public verification helpers."""

from __future__ import annotations

import calendar
import re
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.catalog.types import ProductKind
from sensoria.modules.orders.models import Order, OrderItem
from sensoria.shared.errors import DomainError

from .models import Voucher, VoucherGiftDeliveryJob, VoucherPDFJob

CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_PATTERN = re.compile(
    r"^SEN-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$"
)
VOUCHER_TIMEZONE = ZoneInfo("Europe/Warsaw")
MAX_CODE_ATTEMPTS = 20


def generate_voucher_code(*, chooser: Any = secrets.choice) -> str:
    """Generate an eight-character voucher code using cryptographic randomness."""
    body = "".join(chooser(CODE_ALPHABET) for _ in range(8))
    return f"SEN-{body[:4]}-{body[4:]}"


def add_calendar_months(value: datetime, months: int) -> datetime:
    """Add calendar months, clamping to the final day of a shorter month."""
    if value.tzinfo is None or value.utcoffset() is None or months < 1:
        raise ValueError("Wymagana jest strefowa data i dodatnia liczba miesięcy.")
    absolute_month = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(absolute_month, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def voucher_valid_until_from_delivery(delivered_at: datetime, months: int) -> datetime:
    """Return exclusive UTC boundary after the final valid Warsaw calendar day."""
    if delivered_at.tzinfo is None or delivered_at.utcoffset() is None or months < 1:
        raise ValueError("Wymagana jest strefowa data wysyłki i dodatnia liczba miesięcy.")
    local_day = delivered_at.astimezone(VOUCHER_TIMEZONE)
    final_day = add_calendar_months(local_day, months).date()
    from datetime import time, timedelta

    next_day = final_day + timedelta(days=1)
    return datetime.combine(next_day, time.min, tzinfo=VOUCHER_TIMEZONE).astimezone(UTC)


def effective_voucher_status(
    voucher: Voucher,
    *,
    now: datetime | None = None,
    warning_days: int = 60,
) -> str:
    """Compute the shared state from persisted state and the current instant."""

    if warning_days < 0:
        raise ValueError("warning_days musi być nieujemne.")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if voucher.status == "redeemed" or voucher.redeemed_at is not None:
        return "redeemed"
    if voucher.status == "cancelled":
        return "cancelled"
    if getattr(voucher, "gift_delivery_status", "not_gift") not in {"not_gift", "sent"}:
        return "scheduled"
    if current >= voucher.valid_until.astimezone(UTC):
        return "expired"
    if days_until_expiry(voucher.valid_until, now=current) <= warning_days:
        return "expiring_soon"
    return "active"


def days_until_expiry(valid_until: datetime, *, now: datetime | None = None) -> int:
    """Return remaining local calendar days, not a seconds/86400 approximation."""

    if valid_until.tzinfo is None or valid_until.utcoffset() is None:
        raise ValueError("Termin ważności musi mieć strefę czasową.")
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Bieżący czas musi mieć strefę czasową.")
    return (
        valid_until.astimezone(VOUCHER_TIMEZONE).date()
        - current.astimezone(VOUCHER_TIMEZONE).date()
    ).days


def voucher_public_status(voucher: Voucher, *, now: datetime | None = None) -> str:
    """Compatibility wrapper for the public status endpoint."""

    return effective_voucher_status(voucher, now=now)


async def _insert_voucher_with_retry(
    session: AsyncSession,
    *,
    order_item_id: UUID,
    unit_index: int,
    product_id: UUID,
    variant: dict[str, Any],
    issue_snapshot: dict[str, Any],
    recipient_email: str,
    issued_at: datetime,
    valid_until: datetime,
    code_factory: Any,
) -> Voucher:
    """Retry a code collision inside a savepoint without poisoning the transaction."""
    from sqlalchemy.exc import IntegrityError

    for _attempt in range(MAX_CODE_ATTEMPTS):
        voucher = Voucher(
            code=code_factory(),
            order_item_id=order_item_id,
            unit_index=unit_index,
            product_id=product_id,
            variant=variant,
            status="active",
            issued_at=issued_at,
            valid_until=valid_until,
            recipient_email=recipient_email,
            issue_snapshot=issue_snapshot,
        )
        try:
            async with session.begin_nested():
                session.add(voucher)
                await session.flush()
            return voucher
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint != "uq_vouchers_code":
                raise
    raise DomainError(
        "VOUCHER_CODE_GENERATION_FAILED",
        "Nie udało się bezpiecznie wystawić kodu vouchera. Spróbuj ponownie.",
        503,
    )


async def issue_vouchers_for_paid_order(
    session: AsyncSession,
    order_id: UUID,
    *,
    now: datetime | None = None,
    code_factory: Any = generate_voucher_code,
) -> list[Voucher]:
    """Create voucher records and durable PDF jobs in the caller's transaction.

    The payment integration must call this after authenticating a successful operator event
    and changing the order to ``paid``, before committing that same transaction. This function
    deliberately never commits or starts a separate transaction.
    """
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise DomainError("VOUCHER_ORDER_NOT_FOUND", "Nie znaleziono zamówienia.", 404)
    if order.status != "paid":
        raise DomainError(
            "VOUCHER_PAYMENT_NOT_CONFIRMED",
            "Voucher można wystawić dopiero po potwierdzeniu płatności.",
            409,
        )
    order_items = list(
        (
            await session.scalars(
                select(OrderItem)
                .where(OrderItem.order_id == order_id)
                .order_by(OrderItem.id)
                .with_for_update()
            )
        ).all()
    )
    issued_at = (now or datetime.now(UTC)).astimezone(UTC)
    result: list[Voucher] = []
    for item in order_items:
        variant_snapshot = item.voucher_snapshot
        if variant_snapshot is None:
            continue
        if variant_snapshot.get("kind") != ProductKind.VOUCHER.value:
            continue
        existing = list(
            (
                await session.scalars(
                    select(Voucher)
                    .where(Voucher.order_item_id == item.id)
                    .order_by(Voucher.unit_index)
                )
            ).all()
        )
        by_unit = {voucher.unit_index: voucher for voucher in existing}
        months = variant_snapshot.get("validity_months")
        if isinstance(months, bool) or not isinstance(months, int) or months < 1:
            raise DomainError(
                "VOUCHER_SNAPSHOT_INVALID", "Brak poprawnego snapshotu ważności vouchera.", 500
            )
        gift_snapshot = item.gift_snapshot
        gift_delivery_at = None
        if gift_snapshot is not None:
            try:
                gift_delivery_at = datetime.fromisoformat(gift_snapshot["gift_delivery_at"])
            except (KeyError, TypeError, ValueError):
                raise DomainError(
                    "VOUCHER_GIFT_SNAPSHOT_INVALID", "Snapshot prezentu jest nieprawidłowy.", 500
                ) from None
            if gift_delivery_at.tzinfo is None or gift_delivery_at.utcoffset() is None:
                raise DomainError(
                    "VOUCHER_GIFT_SNAPSHOT_INVALID", "Snapshot prezentu jest nieprawidłowy.", 500
                )
        validity_start = gift_delivery_at or issued_at
        if gift_snapshot is not None and gift_delivery_at is None:
            raise DomainError(
                "VOUCHER_GIFT_SNAPSHOT_INVALID", "Snapshot prezentu jest nieprawidłowy.", 500
            )
        gift_issue_snapshot: dict[str, Any] | None = None
        if gift_snapshot is not None:
            if gift_delivery_at is None:
                raise DomainError(
                    "VOUCHER_GIFT_SNAPSHOT_INVALID", "Snapshot prezentu jest nieprawidłowy.", 500
                )
            gift_issue_snapshot = {
                "recipient_name": gift_snapshot["recipient_name"],
                "recipient_email": gift_snapshot["recipient_email"],
                "dedication": gift_snapshot["dedication"],
                "delivery_mode": gift_snapshot["delivery_mode"],
                "gift_delivery_at": gift_delivery_at.isoformat(),
                "version": gift_snapshot["version"],
            }
        valid_until = voucher_valid_until_from_delivery(validity_start, months)
        for unit_index in range(item.quantity):
            voucher = by_unit.get(unit_index)
            if voucher is None:
                voucher = await _insert_voucher_with_retry(
                    session,
                    order_item_id=item.id,
                    unit_index=unit_index,
                    product_id=item.product_id,
                    variant=variant_snapshot,
                    issue_snapshot={
                        "version": 2 if gift_snapshot is not None else 1,
                        "product_name": item.product_name_snapshot or "Voucher na wizytę",
                        "service_name": variant_snapshot["service_name"],
                        "variant_kind": variant_snapshot["variant_kind"],
                        "validity_months": months,
                        "issued_at": issued_at.isoformat(),
                        "valid_until": valid_until.isoformat(),
                        "recipient_email": order.email.strip().casefold(),
                        **(
                            {"gift": gift_issue_snapshot} if gift_issue_snapshot is not None else {}
                        ),
                    },
                    recipient_email=(
                        gift_snapshot.get("recipient_email") or order.email.strip().casefold()
                        if gift_snapshot is not None
                        else order.email.strip().casefold()
                    ),
                    issued_at=issued_at,
                    valid_until=valid_until,
                    code_factory=code_factory,
                )
                if gift_snapshot is not None:
                    voucher.recipient_name = gift_snapshot["recipient_name"]
                    voucher.dedication = gift_snapshot["dedication"]
                    voucher.gift_delivery_at = gift_delivery_at
                    voucher.gift_delivery_status = (
                        "scheduled"
                        if gift_delivery_at and gift_delivery_at > issued_at
                        else "pending"
                    )
                    voucher.gift_version = int(gift_snapshot.get("version", 1))
                if gift_snapshot is None:
                    session.add(VoucherPDFJob(voucher_id=voucher.id))
                if gift_snapshot is not None:
                    session.add(
                        VoucherGiftDeliveryJob(
                            voucher_id=voucher.id,
                            gift_version=voucher.gift_version,
                            deliver_at=gift_delivery_at or issued_at,
                            recipient_email=(
                                gift_snapshot.get("recipient_email")
                                or order.email.strip().casefold()
                            ),
                            status="pending",
                        )
                    )
                await session.flush()
            elif gift_snapshot is None and (
                await session.scalar(
                    select(VoucherPDFJob.id).where(VoucherPDFJob.voucher_id == voucher.id)
                )
                is None
            ):
                session.add(VoucherPDFJob(voucher_id=voucher.id))
            result.append(voucher)
    return result


async def confirm_gift_delivery_sent(
    session: AsyncSession, voucher_id: UUID, *, sent_at: datetime
) -> Voucher:
    """Finalize validity only after a mail provider confirms acceptance.

    The caller owns the transaction. This is a provider-worker integration point, not called
    by checkout or by a scheduler. It preserves issued_at and the voucher code.
    """
    if sent_at.tzinfo is None or sent_at.utcoffset() is None:
        raise ValueError("Czas wysyłki musi zawierać strefę.")
    paid_order = await session.scalar(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Voucher, Voucher.order_item_id == OrderItem.id)
        .where(Voucher.id == voucher_id)
        .with_for_update(of=Order)
    )
    voucher = await session.scalar(
        select(Voucher).where(Voucher.id == voucher_id).with_for_update()
    )
    if voucher is None or voucher.gift_delivery_status == "not_gift":
        raise DomainError("VOUCHER_GIFT_NOT_FOUND", "Nie znaleziono prezentu do wysłania.", 404)
    if voucher.gift_delivery_status == "sent":
        return voucher
    if voucher.status == "cancelled":
        raise DomainError("VOUCHER_GIFT_CANCELLED", "Wysyłka prezentu została anulowana.", 409)
    if paid_order is None or paid_order.status != "paid":
        raise DomainError("VOUCHER_GIFT_ORDER_NOT_PAID", "Zamówienie nie może zostać wysłane.", 409)
    job = await session.scalar(
        select(VoucherGiftDeliveryJob)
        .where(
            VoucherGiftDeliveryJob.voucher_id == voucher.id,
            VoucherGiftDeliveryJob.gift_version == voucher.gift_version,
        )
        .with_for_update()
    )
    if job is None:
        raise DomainError("VOUCHER_GIFT_JOB_MISSING", "Brak zlecenia wysyłki prezentu.", 409)
    actual_sent_at = sent_at.astimezone(UTC)
    if actual_sent_at < job.deliver_at.astimezone(UTC):
        raise DomainError(
            "VOUCHER_GIFT_NOT_DUE", "Termin wysyłki prezentu jeszcze nie nadszedł.", 409
        )
    months = voucher.issue_snapshot.get("validity_months")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise DomainError("VOUCHER_SNAPSHOT_INVALID", "Brak poprawnej ważności vouchera.", 500)
    voucher.gift_sent_at = actual_sent_at
    voucher.gift_delivery_status = "sent"
    voucher.valid_until = voucher_valid_until_from_delivery(actual_sent_at, months)
    snapshot = dict(voucher.issue_snapshot)
    snapshot["gift"] = {
        **(snapshot.get("gift") or {}),
        "gift_sent_at": actual_sent_at.isoformat(),
        "valid_until": voucher.valid_until.isoformat(),
    }
    snapshot["valid_until"] = voucher.valid_until.isoformat()
    voucher.issue_snapshot = snapshot
    voucher.pdf_file_id = None
    pdf_job = await session.scalar(
        select(VoucherPDFJob).where(VoucherPDFJob.voucher_id == voucher.id).with_for_update()
    )
    if pdf_job is None:
        session.add(VoucherPDFJob(voucher_id=voucher.id, available_at=actual_sent_at))
    else:
        await session.execute(
            update(VoucherPDFJob)
            .where(VoucherPDFJob.voucher_id == voucher.id)
            .values(
                status="pending", available_at=actual_sent_at, completed_at=None, error_code=None
            )
        )
    job.status = "sent"
    job.sent_at = actual_sent_at
    return voucher


def verification_payload(voucher: Voucher, *, now: datetime | None = None) -> dict[str, Any]:
    """Return only the public status and local-calendar expiry date."""
    status = voucher_public_status(voucher, now=now)
    return {
        "status": status,
        "valid_until": (
            voucher.valid_until.astimezone(VOUCHER_TIMEZONE).date().isoformat()
            if status != "scheduled"
            else None
        ),
    }
