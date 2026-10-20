"""Configuration validation tests use isolated values and never load a user .env."""

from secrets import token_urlsafe

import pytest
from pydantic import ValidationError
from sensoria.config import EXAMPLE_SECRET_KEY, Settings

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/sensoria"


def make_settings(**overrides: str) -> Settings:
    values = {
        "DATABASE_URL": DATABASE_URL,
        "ENVIRONMENT": "development",
        "SECRET_KEY": "development-placeholder-is-allowed",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DATABASE_URL", "postgresql://user:private-password@localhost/db"),
        ("DATABASE_URL", "   "),
        ("ENVIRONMENT", "test"),
        ("ENVIRONMENT", "  "),
        ("SECRET_KEY", "  "),
    ],
)
def test_invalid_values_do_not_leak_inputs(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as error:
        make_settings(**{field: value})

    rendered = str(error.value)
    if value.strip():
        assert value.strip() not in rendered
    assert "private-password" not in rendered


@pytest.mark.parametrize(
    "site_url",
    [
        "https://example.test/path",
        "https://user@example.test",
        "//example.test",
    ],
)
def test_public_site_origin_rejects_paths_credentials_and_relative_urls(site_url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(SITE_URL=site_url)


def test_production_public_site_origin_requires_https() -> None:
    with pytest.raises(ValidationError):
        make_settings(
            ENVIRONMENT="production",
            SECRET_KEY="production-test-key-that-is-at-least-32-characters-long",
            SITE_URL="http://example.test",
        )


@pytest.mark.parametrize("field", ["DATABASE_URL", "ENVIRONMENT", "SECRET_KEY"])
def test_required_values_are_required(field: str, monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "DATABASE_URL": DATABASE_URL,
        "ENVIRONMENT": "development",
        "SECRET_KEY": "development-placeholder-is-allowed",
    }
    values.pop(field)
    monkeypatch.delenv(field, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


@pytest.mark.parametrize(
    "secret",
    [EXAMPLE_SECRET_KEY, "x" * 31, "this-is-a-placeholder-key-that-is-long-enough"],
)
def test_production_rejects_short_and_placeholder_keys(secret: str) -> None:
    if secret == EXAMPLE_SECRET_KEY:
        assert len(secret) > 32

    with pytest.raises(ValidationError) as error:
        make_settings(ENVIRONMENT="production", SECRET_KEY=secret)

    assert "SECRET_KEY" in str(error.value)
    assert secret not in str(error.value)


def test_production_accepts_long_random_key() -> None:
    settings = make_settings(ENVIRONMENT="production", SECRET_KEY=token_urlsafe(48))

    assert settings.ENVIRONMENT == "production"


def test_blank_optional_integrations_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from sensoria.config import Settings
    from sensoria.modules.mail.transport import mail_configured
    from sensoria.modules.payments.stripe_client import stripe_configured

    values = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/d",
        "ENVIRONMENT": "development",
        "SECRET_KEY": "test-only-placeholder-not-a-secret",
        "STRIPE_SECRET_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "   ",
        "SMTP_HOST": "",
        "MAIL_FROM": "",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.STRIPE_SECRET_KEY is None and settings.STRIPE_WEBHOOK_SECRET is None
    assert not stripe_configured(settings) and not mail_configured(settings)
