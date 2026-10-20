"""Pure rules for the fail-closed voucher reminder contract."""

from datetime import UTC, datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sensoria.modules.vouchers.models import Voucher
from sensoria.modules.vouchers.reminder_integrations import (
    configured_queue,
    configured_reminder_consent_reader,
)
from sensoria.modules.vouchers.reminders import (
    DEFAULT_REMINDER_SETTINGS,
    ReminderSettings,
    VoucherReminderConfigurationError,
    build_reminder_variables,
    due_threshold,
    next_local_run,
    validate_reminder_settings,
)


def test_default_settings_are_two_daily_local_reminder_thresholds() -> None:
    settings = validate_reminder_settings(DEFAULT_REMINDER_SETTINGS)

    assert settings.threshold_days == (30, 7)
    assert settings.local_time == time(9, 0)
    assert settings.timezone.key == "Europe/Warsaw"
    assert settings.max_messages_per_run == 200


@pytest.mark.parametrize(
    "value",
    [
        {
            "threshold_days": [30, 30],
            "local_time": "09:00",
            "timezone": "Europe/Warsaw",
            "max_messages_per_run": 10,
        },
        {
            "threshold_days": [7, 30],
            "local_time": "09:00",
            "timezone": "Europe/Warsaw",
            "max_messages_per_run": 10,
        },
        {
            "threshold_days": [0],
            "local_time": "09:00",
            "timezone": "Europe/Warsaw",
            "max_messages_per_run": 10,
        },
        {
            "threshold_days": [30],
            "local_time": "25:00",
            "timezone": "Europe/Warsaw",
            "max_messages_per_run": 10,
        },
        {
            "threshold_days": [30],
            "local_time": "09:00",
            "timezone": "UTC",
            "max_messages_per_run": 10,
        },
        {
            "threshold_days": [30],
            "local_time": "09:00",
            "timezone": "Europe/Warsaw",
            "max_messages_per_run": 0,
        },
    ],
)
def test_invalid_operator_settings_are_rejected(value: object) -> None:
    with pytest.raises(VoucherReminderConfigurationError):
        validate_reminder_settings(value)


def test_catch_up_uses_the_most_current_threshold_only() -> None:
    thresholds = (30, 7)

    assert due_threshold(31, thresholds) is None
    assert due_threshold(30, thresholds) == 30
    assert due_threshold(8, thresholds) == 30
    assert due_threshold(7, thresholds) == 7
    assert due_threshold(1, thresholds) == 7
    assert due_threshold(0, thresholds) == 7


def test_scheduler_uses_fixed_local_time_across_dst() -> None:
    settings = ReminderSettings((30, 7), time(9, 0), ZoneInfo("Europe/Warsaw"), 200)

    before_spring_dst = datetime(2026, 3, 28, 12, tzinfo=UTC)
    spring_next = next_local_run(before_spring_dst, settings)
    assert spring_next == datetime(2026, 3, 29, 7, tzinfo=UTC)
    assert spring_next.astimezone(settings.timezone).hour == 9

    before_autumn_dst = datetime(2026, 10, 24, 12, tzinfo=UTC)
    autumn_next = next_local_run(before_autumn_dst, settings)
    assert autumn_next == datetime(2026, 10, 25, 8, tzinfo=UTC)
    assert autumn_next.astimezone(settings.timezone).hour == 9


def test_consent_reader_is_connected_while_mail_queue_fails_closed() -> None:
    assert configured_reminder_consent_reader() is not None
    assert configured_queue() is None


def test_message_variables_use_voucher_snapshot_and_configured_origin() -> None:
    voucher = Voucher(
        code="SEN-4K2P-9WQ2",
        order_item_id=uuid4(),
        unit_index=0,
        product_id=uuid4(),
        variant={"variant_kind": "online"},
        status="active",
        issued_at=datetime(2026, 1, 1, tzinfo=UTC),
        valid_until=datetime(2027, 1, 1, 22, 59, tzinfo=UTC),
        recipient_email="buyer@example.com",
        issue_snapshot={"service_name": "Konsultacja online"},
    )

    variables = build_reminder_variables(
        voucher,
        now=datetime(2026, 12, 1, tzinfo=UTC),
        site_url="https://sensoria.example/",
    )

    assert variables["service_name"] == "Konsultacja online"
    assert variables["code"] == "SEN-4K2P-9WQ2"
    assert variables["valid_until"] == "01.01.2027"
    assert variables["account_url"] == "https://sensoria.example/konto/vouchery"
    assert variables["days_remaining"] == 31
