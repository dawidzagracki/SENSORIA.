"""Public, validated presentation settings for an empty catalog search."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEARCH_PRESENTATION_SETTING_KEY = "catalog.search_empty.v1"

_EMAIL_PATTERN = re.compile(r"^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$")
_PHONE_PATTERN = re.compile(r"^[+0-9(). -]{7,32}$")


class SearchPresentationSettings(BaseModel):
    """Only non-secret fields required by the public no-results view."""

    model_config = ConfigDict(extra="forbid")

    suggested_queries: list[str] = Field(min_length=1, max_length=8)
    contact_email: str | None = None
    contact_phone: str | None = None

    @field_validator("suggested_queries")
    @classmethod
    def validate_suggested_queries(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 80 for value in cleaned):
            raise ValueError("suggested queries must contain 1–80 characters")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("suggested queries must be unique")
        return cleaned

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) > 254 or not _EMAIL_PATTERN.fullmatch(cleaned):
            raise ValueError("contact email has an invalid format")
        return cleaned

    @field_validator("contact_phone")
    @classmethod
    def validate_contact_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not _PHONE_PATTERN.fullmatch(cleaned) or sum(char.isdigit() for char in cleaned) < 7:
            raise ValueError("contact phone has an invalid format")
        return cleaned


DEFAULT_SEARCH_PRESENTATION = SearchPresentationSettings(
    suggested_queries=[
        "integracja sensoryczna",
        "terapia ręki",
        "nadwrażliwość",
        "voucher",
    ],
    contact_email=None,
    contact_phone=None,
)
