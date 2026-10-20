"""Voucher account status uses one timezone-aware effective-state rule."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from sensoria.modules.vouchers.models import Voucher
from sensoria.modules.vouchers.service import (
    days_until_expiry,
    effective_voucher_status,
)


def test_expiry_days_use_warsaw_calendar_dates_across_dst() -> None:
    now = datetime(2026, 3, 28, 23, 30, tzinfo=UTC)
    until = datetime(2026, 3, 29, 22, 0, tzinfo=UTC)

    assert days_until_expiry(until, now=now) == 1


@pytest.mark.parametrize(
    ("status", "redeemed_at", "valid_until", "expected"),
    [
        ("active", None, datetime(2026, 12, 31, tzinfo=UTC), "active"),
        ("active", None, datetime(2026, 7, 31, tzinfo=UTC), "expiring_soon"),
        ("active", None, datetime(2026, 3, 1, tzinfo=UTC), "expired"),
        (
            "redeemed",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 12, 31, tzinfo=UTC),
            "redeemed",
        ),
        ("cancelled", None, datetime(2026, 12, 31, tzinfo=UTC), "cancelled"),
    ],
)
def test_effective_status_prioritizes_terminal_states_and_time(
    status: str,
    redeemed_at: datetime | None,
    valid_until: datetime,
    expected: str,
) -> None:
    voucher = cast(
        Voucher,
        SimpleNamespace(status=status, redeemed_at=redeemed_at, valid_until=valid_until),
    )
    now = datetime(2026, 6, 1, tzinfo=UTC)

    assert effective_voucher_status(voucher, now=now) == expected
