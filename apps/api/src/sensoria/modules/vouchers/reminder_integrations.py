"""Fail-closed dependency points for not-yet-implemented stages [60], [62] and [63]."""

from .reminders import VoucherReminderConsentReader, VoucherReminderQueue


def configured_reminder_consent_reader() -> VoucherReminderConsentReader | None:
    """Return the append-only [60] consent reader; checks fail closed when absent."""
    from .reminder_consent import AccountVoucherReminderConsentReader

    return AccountVoucherReminderConsentReader()


def configured_queue() -> VoucherReminderQueue | None:
    """Return the transactional [62]/[63] queue adapter when implemented."""
    return None
