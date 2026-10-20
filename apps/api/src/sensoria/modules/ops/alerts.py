"""Owner alerts delivered through the mail outbox; configuration lives in app settings."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.modules.mail.outbox import enqueue_mail
from sensoria.shared.app_settings import AppSetting

logger = logging.getLogger("sensoria.ops.alerts")
ALERTS_KEY = "ops.alerts.v1"


async def alert_email(session: AsyncSession) -> str | None:
    setting = await session.scalar(select(AppSetting).where(AppSetting.key == ALERTS_KEY))
    value = setting.value.get("email") if setting and isinstance(setting.value, dict) else None
    if isinstance(value, str) and value.count("@") == 1 and "." in value.rsplit("@", 1)[-1]:
        return value.strip()
    return None


async def notify_owner(
    session: AsyncSession, *, key: str, title: str, lines: list[str], link: str | None = None
) -> bool:
    """Queue one alert per idempotency key; without configured recipient it only logs."""
    recipient = await alert_email(session)
    if recipient is None:
        logger.warning("Alert operacyjny bez skonfigurowanego odbiorcy [%s].", key.split(":")[0])
        return False
    await enqueue_mail(
        session,
        template_key="ops_alert",
        recipient=recipient,
        variables={"title": title, "lines": lines, "link": link},
        idempotency_key=f"ops-alert:{key}",
    )
    return True


def describe(**fields: Any) -> list[str]:
    return [f"{name}: {value}" for name, value in fields.items()]
