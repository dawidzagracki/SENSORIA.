"""Administrative voucher operations; each mutation locks the row and writes the ledger."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .models import Voucher, VoucherEvent, VoucherExtensionRequest, VoucherPDFJob
from .service import VOUCHER_TIMEZONE, effective_voucher_status

MAX_EXTENSION_DAYS = 800


def end_of_local_day(day: date) -> datetime:
    """Validity ends at the close of the chosen Warsaw calendar day (inclusive)."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=VOUCHER_TIMEZONE).astimezone(
        UTC
    )


async def _locked(session: AsyncSession, voucher_id: UUID) -> Voucher:
    voucher = await session.scalar(
        select(Voucher).where(Voucher.id == voucher_id).with_for_update()
    )
    if voucher is None:
        raise DomainError("VOUCHER_NOT_FOUND", "Nie znaleziono vouchera.", 404)
    return voucher


def _event(
    voucher: Voucher,
    action: str,
    admin_id: UUID,
    *,
    occurred_at: datetime,
    performed_by: str | None = None,
    note: str | None = None,
    previous: datetime | None = None,
    new: datetime | None = None,
) -> VoucherEvent:
    return VoucherEvent(
        voucher_id=voucher.id,
        action=action,
        admin_id=admin_id,
        performed_by=performed_by,
        occurred_at=occurred_at,
        note=note,
        previous_valid_until=previous,
        new_valid_until=new,
    )


def _audit(voucher: Voucher, admin_id: UUID, action: str) -> AuditLog:
    return AuditLog(
        actor_type=ActorType.ADMINISTRATOR,
        actor_id=admin_id,
        entity_type="voucher",
        entity_id=voucher.id,
        action=f"voucher.{action}",
        payload={"code": voucher.code},
    )


async def redeem(
    session: AsyncSession,
    voucher_id: UUID,
    *,
    admin_id: UUID,
    performed_by: str,
    occurred_at: datetime | None = None,
    note: str | None = None,
) -> Voucher:
    voucher = await _locked(session, voucher_id)
    now = datetime.now(UTC)
    moment = (occurred_at or now).astimezone(UTC)
    if moment > now + timedelta(minutes=5):
        raise DomainError(
            "VOUCHER_REDEEM_FUTURE", "Data realizacji nie może być z przyszłości.", 422
        )
    status = effective_voucher_status(voucher, now=moment)
    if status not in {"active", "expiring_soon"}:
        messages = {
            "redeemed": "Voucher został już zrealizowany.",
            "expired": "Voucher wygasł; przedłuż go przed realizacją.",
            "cancelled": "Voucher został anulowany.",
            "scheduled": "Voucher prezentowy nie został jeszcze wysłany.",
        }
        raise DomainError(
            "VOUCHER_NOT_REDEEMABLE",
            messages.get(status, "Voucher nie może być zrealizowany."),
            409,
        )
    voucher.status = "redeemed"
    voucher.redeemed_at = moment
    voucher.redeemed_by = performed_by.strip()[:200]
    session.add(
        _event(
            voucher,
            "redeemed",
            admin_id,
            occurred_at=moment,
            performed_by=voucher.redeemed_by,
            note=note,
        )
    )
    session.add(_audit(voucher, admin_id, "redeemed"))
    await session.flush()
    return voucher


async def revert_redemption(
    session: AsyncSession, voucher_id: UUID, *, admin_id: UUID, reason: str
) -> Voucher:
    voucher = await _locked(session, voucher_id)
    if voucher.status != "redeemed":
        raise DomainError("VOUCHER_NOT_REDEEMED", "Voucher nie jest zrealizowany.", 409)
    voucher.status = "active"
    voucher.redeemed_at = None
    voucher.redeemed_by = None
    now = datetime.now(UTC)
    session.add(_event(voucher, "redemption_reverted", admin_id, occurred_at=now, note=reason))
    session.add(_audit(voucher, admin_id, "redemption_reverted"))
    await session.flush()
    return voucher


async def cancel(
    session: AsyncSession, voucher_id: UUID, *, admin_id: UUID, reason: str
) -> Voucher:
    voucher = await _locked(session, voucher_id)
    if voucher.status == "cancelled":
        return voucher
    if voucher.status == "redeemed":
        raise DomainError(
            "VOUCHER_ALREADY_REDEEMED", "Zrealizowanego vouchera najpierw cofnij realizację.", 409
        )
    voucher.status = "cancelled"
    session.add(_event(voucher, "cancelled", admin_id, occurred_at=datetime.now(UTC), note=reason))
    session.add(_audit(voucher, admin_id, "cancelled"))
    await session.flush()
    return voucher


async def extend(
    session: AsyncSession,
    voucher_id: UUID,
    *,
    admin_id: UUID,
    new_last_day: date,
    reason: str,
) -> Voucher:
    voucher = await _locked(session, voucher_id)
    if voucher.status in {"redeemed", "cancelled"}:
        raise DomainError("VOUCHER_NOT_EXTENDABLE", "Tego vouchera nie można przedłużyć.", 409)
    new_valid_until = end_of_local_day(new_last_day)
    now = datetime.now(UTC)
    if new_valid_until <= voucher.valid_until:
        raise DomainError(
            "VOUCHER_EXTENSION_NOT_LATER", "Nowa data musi być późniejsza niż obecna.", 422
        )
    if new_valid_until > now + timedelta(days=MAX_EXTENSION_DAYS):
        raise DomainError("VOUCHER_EXTENSION_TOO_FAR", "Wybrana data jest zbyt odległa.", 422)
    previous = voucher.valid_until
    voucher.valid_until = new_valid_until
    voucher.status = "active"
    snapshot = dict(voucher.issue_snapshot)
    snapshot["valid_until"] = new_valid_until.isoformat()
    voucher.issue_snapshot = snapshot
    voucher.pdf_file_id = None  # the PDF prints the validity date, so it must be re-rendered
    job = await session.scalar(
        select(VoucherPDFJob).where(VoucherPDFJob.voucher_id == voucher.id).with_for_update()
    )
    if job is None:
        session.add(VoucherPDFJob(voucher_id=voucher.id))
    else:
        await session.execute(
            update(VoucherPDFJob)
            .where(VoucherPDFJob.voucher_id == voucher.id)
            .values(status="pending", completed_at=None, error_code=None, attempts=0)
        )
    session.add(
        _event(
            voucher,
            "extended",
            admin_id,
            occurred_at=now,
            note=reason,
            previous=previous,
            new=new_valid_until,
        )
    )
    session.add(_audit(voucher, admin_id, "extended"))
    await session.flush()
    return voucher


async def decide_extension_request(
    session: AsyncSession,
    request_id: UUID,
    *,
    admin_id: UUID,
    approve: bool,
    new_last_day: date | None,
    note: str,
) -> VoucherExtensionRequest:
    record = await session.scalar(
        select(VoucherExtensionRequest)
        .where(VoucherExtensionRequest.id == request_id)
        .with_for_update()
    )
    if record is None:
        raise DomainError("EXTENSION_REQUEST_NOT_FOUND", "Nie znaleziono prośby.", 404)
    if record.status != "pending":
        raise DomainError("EXTENSION_REQUEST_DECIDED", "Prośba została już rozpatrzona.", 409)
    if approve:
        if new_last_day is None:
            raise DomainError("EXTENSION_DATE_REQUIRED", "Podaj nową datę ważności.", 422)
        await extend(
            session, record.voucher_id, admin_id=admin_id, new_last_day=new_last_day, reason=note
        )
    record.status = "approved" if approve else "rejected"
    record.decided_at = datetime.now(UTC)
    record.decision_note = note[:2000]
    await session.flush()
    return record
