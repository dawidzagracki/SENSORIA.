"""Idempotent seeding for explicitly approved non-secret application settings."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sensoria.database import SessionFactory
from sensoria.modules.catalog.homepage import (
    DEFAULT_HOMEPAGE_CONTENT,
    HOMEPAGE_SETTING_KEY,
)
from sensoria.modules.catalog.search_presentation import (
    DEFAULT_SEARCH_PRESENTATION,
    SEARCH_PRESENTATION_SETTING_KEY,
)
from sensoria.modules.vouchers.reminders import (
    DEFAULT_REMINDER_SETTINGS,
    REMINDER_SETTINGS_KEY,
)
from sensoria.shared.app_settings import AppSetting


@dataclass(frozen=True)
class SettingSeed:
    """One approved default setting; values must be JSON-serializable and non-secret."""

    key: str
    value: Any
    description: str


# No business defaults are seeded until their values are specified by the project.
DEFAULT_SETTINGS: tuple[SettingSeed, ...] = (
    SettingSeed(
        key=REMINDER_SETTINGS_KEY,
        value=DEFAULT_REMINDER_SETTINGS,
        description=(
            "Progi, pora lokalna, strefa i limit przebiegu przypomnień o voucherach. "
            "Wysyłka wymaga integracji zgód [60] i kolejki [62]/[63]."
        ),
    ),
    SettingSeed(
        key=HOMEPAGE_SETTING_KEY,
        value=DEFAULT_HOMEPAGE_CONTENT.model_dump(mode="json"),
        description="Redakcyjne treści publicznej strony głównej; bez sekretów.",
    ),
    SettingSeed(
        key=SEARCH_PRESENTATION_SETTING_KEY,
        value=DEFAULT_SEARCH_PRESENTATION.model_dump(mode="json"),
        description="Publiczne podpowiedzi i opcjonalne dane kontaktowe pustego wyszukiwania.",
    ),
)


async def seed_settings(
    session_factory: async_sessionmaker[AsyncSession] = SessionFactory,
    defaults: Sequence[SettingSeed] = DEFAULT_SETTINGS,
) -> int:
    """Insert missing defaults without overwriting values edited by an operator."""

    inserted = 0
    async with session_factory.begin() as session:
        for setting in defaults:
            statement = (
                insert(AppSetting)
                .values(
                    key=setting.key,
                    value=setting.value,
                    description=setting.description,
                )
                .on_conflict_do_nothing(index_elements=[AppSetting.key])
                .returning(AppSetting.id)
            )
            result = await session.execute(statement)
            inserted += len(result.scalars().all())
    return inserted


async def _main() -> None:
    count = await seed_settings()
    print(f"Seed ustawień zakończony. Dodano {count} nowych ustawień.")


if __name__ == "__main__":
    asyncio.run(_main())
