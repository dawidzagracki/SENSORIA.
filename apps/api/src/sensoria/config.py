"""Application settings loaded from the repository-root environment file."""

import ipaddress
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_CONFIG_PATH = Path(__file__).resolve()
REPOSITORY_ROOT = (
    _CONFIG_PATH.parents[4] if len(_CONFIG_PATH.parents) > 4 else _CONFIG_PATH.parents[2]
)
DEFAULT_ENV_FILE = REPOSITORY_ROOT / ".env"
SETTINGS_ENV_FILE = Path(os.environ.get("SENSORIA_ENV_FILE", DEFAULT_ENV_FILE))
EXAMPLE_SECRET_KEY = "replace-with-a-local-random-value"
KNOWN_SECRET_PLACEHOLDERS = {
    EXAMPLE_SECRET_KEY,
    "example-only-change-before-use",
    "change-me-before-local-use",
    "test-only-placeholder-not-a-secret",
    "changeme",
    "change-me",
    "your-secret-key",
}


class SettingsError(ValueError):
    """Raised with a safe Polish message when required settings are invalid."""


class Settings(BaseSettings):
    """Required configuration; sensitive settings are redacted by Pydantic."""

    model_config = SettingsConfigDict(
        env_file=SETTINGS_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    DATABASE_URL: SecretStr
    ENVIRONMENT: Literal["development", "production"]
    SECRET_KEY: SecretStr
    SITE_URL: str | None = None
    SITE_OG_IMAGE: str | None = None
    CATALOG_CACHE_TTL_SECONDS: int = Field(default=30, ge=0, le=300)
    CART_CLEANUP_INTERVAL_SECONDS: int = Field(default=3600, ge=60, le=86400)
    CART_CLEANUP_BATCH_SIZE: int = Field(default=500, ge=1, le=5000)
    SAMPLE_STORAGE_ROOT: str = "/app/uploads/samples"
    UPLOADS_ROOT: str = "/app/uploads"
    SAMPLE_OPEN_LIMIT: int = Field(default=12, ge=1, le=1000)
    SAMPLE_OPEN_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    SAMPLE_STREAM_LIMIT: int = Field(default=120, ge=1, le=10000)
    SAMPLE_STREAM_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    SAMPLE_SESSION_TTL_SECONDS: int = Field(default=1800, ge=60, le=86400)
    SAMPLE_SESSION_REQUEST_LIMIT: int = Field(default=24, ge=1, le=200)
    TRUSTED_PROXY_CIDRS: str = ""
    LOGIN_LINK_EMAIL_LIMIT: int = Field(default=4, ge=2, le=20)
    LOGIN_LINK_IP_LIMIT: int = Field(default=20, ge=3, le=200)
    LOGIN_LINK_WINDOW_SECONDS: int = Field(default=3600, ge=60, le=86400)
    LOGIN_LINK_COOLDOWN_SECONDS: int = Field(default=900, ge=60, le=86400)
    LOGIN_LINK_INVALID_LIMIT: int = Field(default=20, ge=3, le=200)
    INPOST_POINTS_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=20)

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, value: str) -> str:
        """Reject malformed proxy lists without exposing configuration values."""

        if not value.strip():
            return ""
        try:
            for item in value.split(","):
                ipaddress.ip_network(item.strip(), strict=False)
        except ValueError:
            raise ValueError("invalid") from None
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("invalid")

        try:
            parsed_url = make_url(value)
        except Exception:
            raise ValueError("invalid") from None

        if (
            parsed_url.drivername != "postgresql+asyncpg"
            or not parsed_url.username
            or parsed_url.password is None
            or not parsed_url.password
            or not parsed_url.host
            or not parsed_url.database
        ):
            raise ValueError("invalid")

        return value

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(
        cls,
        value: SecretStr,
        info: ValidationInfo,
    ) -> SecretStr:
        secret = value.get_secret_value()
        if not secret.strip():
            raise ValueError("empty")

        environment = info.data.get("ENVIRONMENT")
        if environment == "production":
            normalized_secret = secret.strip().casefold()
            if (
                len(secret) < 32
                or normalized_secret in {item.casefold() for item in KNOWN_SECRET_PLACEHOLDERS}
                or "placeholder" in normalized_secret
                or "change-me" in normalized_secret
                or "example" in normalized_secret
            ):
                raise ValueError("invalid production key")

        return value

    @field_validator("SITE_OG_IMAGE", mode="before")
    @classmethod
    def validate_site_og_image(cls, value: Any) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or value != value.strip():
            raise ValueError("invalid")
        parsed = urlsplit(value)
        if value.startswith("/") and not value.startswith("//"):
            return value
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("invalid")
        return value

    @field_validator("SITE_URL", mode="before")
    @classmethod
    def validate_site_url(cls, value: Any, info: ValidationInfo) -> str | None:
        """Validate the configured public origin used in canonical links and voucher QR."""

        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, str) or value != value.strip():
            raise ValueError("invalid")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("invalid")
        if info.data.get("ENVIRONMENT") == "production" and parsed.scheme != "https":
            raise ValueError("invalid")
        return value.rstrip("/")


def _safe_validation_message(error: ValidationError) -> str:
    """Translate Pydantic errors using field names only, never rejected values."""

    errors = error.errors(include_input=False)
    field_names = {str(detail["loc"][0]) for detail in errors if detail.get("loc")}

    missing = [str(detail["loc"][0]) for detail in errors if detail["type"] == "missing"]
    if missing:
        names = ", ".join(sorted(set(missing)))
        return f"Brak wymaganej zmiennej środowiskowej: {names}."

    if "DATABASE_URL" in field_names:
        return (
            "Zmienna DATABASE_URL musi używać formatu "
            "postgresql+asyncpg://user:password@host:5432/database."
        )
    if "ENVIRONMENT" in field_names:
        return "Zmienna ENVIRONMENT musi mieć wartość development albo production."
    if "SECRET_KEY" in field_names:
        return (
            "Zmienna SECRET_KEY jest nieprawidłowa; w production musi zawierać "
            "co najmniej 32 znaki losowego klucza."
        )

    names = ", ".join(sorted(field_names)) or "konfiguracja aplikacji"
    return f"Nieprawidłowa konfiguracja zmiennych: {names}."


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings and replace value-bearing Pydantic errors with safe messages."""

    try:
        return Settings()  # type: ignore[call-arg]  # BaseSettings reads values from its sources.
    except ValidationError as error:
        raise SettingsError(_safe_validation_message(error)) from None
