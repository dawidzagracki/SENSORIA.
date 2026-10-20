"""Owner-editable business settings with per-key validation (no raw SQL needed)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator
from sqlalchemy import select

from sensoria.modules.documents.service import SELLER_SETTING_KEY, SellerSettings
from sensoria.modules.ops.alerts import ALERTS_KEY
from sensoria.modules.orders.delivery import DELIVERY_SETTING_KEY, DeliveryPolicy
from sensoria.modules.reviews.service import SETTINGS_KEY as REVIEW_KEY
from sensoria.shared.app_settings import AppSetting
from sensoria.shared.audit_log import ActorType, AuditLog
from sensoria.shared.errors import DomainError

from .common import Owner, SessionDependency

router = APIRouter(prefix="/settings", tags=["admin-settings"])
PUBLIC_CONTACT_KEY = "vouchers.public.v1"


class AlertSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1] or " " in value:
            raise ValueError("Podaj prawidłowy adres e-mail.")
        return value


class PublicContactSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    booking_url: str | None = Field(default=None, max_length=500)
    booking_instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("booking_url")
    @classmethod
    def https_only(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        parts = urlsplit(value.strip())
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError("Adres rezerwacji musi zaczynać się od https://.")
        return value.strip()


class ReviewRequestSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delay_days: StrictInt = Field(ge=1, le=90)


REGISTRY: dict[str, tuple[type[BaseModel], str]] = {
    SELLER_SETTING_KEY: (SellerSettings, "Dane sprzedawcy na paragonach i fakturach"),
    DELIVERY_SETTING_KEY: (DeliveryPolicy, "Koszty dostawy, progi i VAT dostawy (w groszach)"),
    ALERTS_KEY: (AlertSettings, "Adres e-mail do alertów operacyjnych"),
    PUBLIC_CONTACT_KEY: (PublicContactSettings, "Dane kontaktowe i rezerwacja wizyt"),
    REVIEW_KEY: (ReviewRequestSettings, "Opóźnienie próśb o opinię (dni)"),
}


class SettingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: dict[str, Any]


@router.get("")
async def list_settings(session: SessionDependency, _admin: Owner) -> dict[str, Any]:
    rows = {
        s.key: s
        for s in (
            await session.scalars(select(AppSetting).where(AppSetting.key.in_(list(REGISTRY))))
        ).all()
    }
    return {
        "items": [
            {
                "key": key,
                "label": label,
                "value": rows[key].value if key in rows else None,
            }
            for key, (_model, label) in REGISTRY.items()
        ]
    }


@router.put("/{key}")
async def save_setting(
    key: str, payload: SettingInput, session: SessionDependency, admin: Owner
) -> dict[str, Any]:
    entry = REGISTRY.get(key)
    if entry is None:
        raise DomainError("SETTING_UNKNOWN", "Tego ustawienia nie można edytować w panelu.", 404)
    model, label = entry
    try:
        valid = model.model_validate(payload.value)
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        where = ".".join(str(part) for part in first.get("loc", ())) or "wartość"
        raise DomainError(
            "SETTING_INVALID", f"Nieprawidłowe ustawienie ({where}): {first.get('msg', '')}", 422
        ) from None
    stored = valid.model_dump(mode="json")
    async with session.begin():
        setting = await session.scalar(
            select(AppSetting).where(AppSetting.key == key).with_for_update()
        )
        if setting is None:
            setting = AppSetting(key=key, value=stored, description=label)
            session.add(setting)
        else:
            setting.value = stored
        await session.flush()
        session.add(
            AuditLog(
                actor_type=ActorType.ADMINISTRATOR,
                actor_id=admin.id,
                entity_type="app_setting",
                entity_id=setting.id,
                action="setting.saved",
                payload={"key": key},
            )
        )
    return {"key": key, "value": stored}
