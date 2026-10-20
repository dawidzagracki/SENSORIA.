from datetime import UTC, date, datetime
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sensoria.modules.orders.schemas import GiftOrderItemInput
from sensoria.modules.vouchers.gifts import scheduled_delivery_at
from sensoria.modules.vouchers.models import Voucher
from sensoria.modules.vouchers.service import (
    VOUCHER_TIMEZONE,
    effective_voucher_status,
    voucher_valid_until_from_delivery,
)


def test_gift_checkout_contract_allows_optional_email_and_dedication() -> None:
    gift = GiftOrderItemInput(
        cart_item_id=uuid4(),
        recipient_name="  Żaneta   Nowak ",
        recipient_email=" ",
        dedication="Sto lat!",
        delivery_mode="immediate",
    )
    assert gift.recipient_name == "Żaneta Nowak"
    assert gift.recipient_email is None
    assert gift.dedication == "Sto lat!"


def test_gift_dedication_filters_control_characters_and_enforces_300() -> None:
    gift = GiftOrderItemInput(
        cart_item_id=uuid4(),
        recipient_name="Ala",
        dedication="A\x00B\nC",
        delivery_mode="immediate",
    )
    assert gift.dedication == "AB\nC"
    with pytest.raises(ValidationError):
        GiftOrderItemInput(
            cart_item_id=uuid4(),
            recipient_name="Ala",
            dedication="x" * 301,
            delivery_mode="immediate",
        )


def test_scheduled_delivery_uses_warsaw_local_time_and_today_asap() -> None:
    now = datetime(2026, 10, 16, 8, 30, tzinfo=UTC)
    scheduled = scheduled_delivery_at(date(2026, 10, 17), now=now)
    assert scheduled.astimezone(VOUCHER_TIMEZONE).isoformat() == "2026-10-17T09:00:00+02:00"
    today_after_send_time = datetime(2026, 10, 16, 8, 30, tzinfo=UTC)  # 10:30 in Warsaw.
    asap = scheduled_delivery_at(date(2026, 10, 16), now=today_after_send_time)
    assert asap == today_after_send_time
    with pytest.raises(Exception, match="dzisiejszy dzień"):
        scheduled_delivery_at(date(2026, 10, 15), now=now)


def test_voucher_validity_starts_from_actual_send_and_ends_after_local_day() -> None:
    sent = datetime(2024, 2, 29, 12, tzinfo=UTC)
    valid_until = voucher_valid_until_from_delivery(sent, 12)
    assert valid_until.astimezone(VOUCHER_TIMEZONE).isoformat() == "2025-03-01T00:00:00+01:00"


def test_unsent_gift_is_not_effectively_active() -> None:
    class GiftVoucher:
        status = "active"
        redeemed_at = None
        gift_delivery_status = "scheduled"
        valid_until = datetime(2027, 1, 1, tzinfo=UTC)

    assert (
        effective_voucher_status(
            cast(Voucher, GiftVoucher()), now=datetime(2026, 10, 16, tzinfo=UTC)
        )
        == "scheduled"
    )
