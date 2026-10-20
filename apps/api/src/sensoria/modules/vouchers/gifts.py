"""Gift checkout normalization and scheduled-delivery policy helpers."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.shared.app_settings import AppSetting
from sensoria.shared.errors import DomainError

from .service import VOUCHER_TIMEZONE

GIFT_SETTINGS_KEY = "vouchers.gifts.v1"
DEFAULT_GIFT_SETTINGS: dict[str, Any] = {
    "local_send_time": "09:00",
    "timezone": "Europe/Warsaw",
    "dedication_max_length": 300,
}


async def load_gift_settings(session: AsyncSession) -> dict[str, Any]:
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == GIFT_SETTINGS_KEY))
    values = setting.value if setting is not None and isinstance(setting.value, dict) else {}
    local_time = values.get("local_send_time", DEFAULT_GIFT_SETTINGS["local_send_time"])
    zone = values.get("timezone", DEFAULT_GIFT_SETTINGS["timezone"])
    if not isinstance(local_time, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", local_time
    ):
        raise DomainError(
            "GIFT_SETTINGS_INVALID", "Konfiguracja wysyłki prezentów jest nieprawidłowa.", 503
        )
    if zone != "Europe/Warsaw":
        raise DomainError(
            "GIFT_SETTINGS_INVALID", "Strefa wysyłki prezentów musi być Europe/Warsaw.", 503
        )
    if values.get("dedication_max_length", 300) != 300:
        raise DomainError("GIFT_SETTINGS_INVALID", "Limit dedykacji musi wynosić 300 znaków.", 503)
    return {"local_send_time": local_time, "timezone": zone, "dedication_max_length": 300}


def scheduled_delivery_at(
    delivery_date: date,
    *,
    now: datetime,
    local_time: str = "09:00",
    timezone: ZoneInfo = VOUCHER_TIMEZONE,
) -> datetime:
    """Resolve an ISO calendar date to configured local time; elapsed today means ASAP."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Bieżący czas musi zawierać strefę.")
    local_now = now.astimezone(timezone)
    if delivery_date < local_now.date():
        raise DomainError("GIFT_DATE_PAST", "Wybierz dzisiejszy dzień lub datę z przyszłości.", 422)
    hour, minute = (int(part) for part in local_time.split(":"))
    requested = datetime.combine(delivery_date, time(hour, minute), tzinfo=timezone)
    if delivery_date == local_now.date() and requested <= local_now:
        requested = local_now
    return requested.astimezone(UTC)
