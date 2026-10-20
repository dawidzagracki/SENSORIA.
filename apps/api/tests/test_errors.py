"""Tests for global error response handling using test-only routes."""

import pytest
from httpx import ASGITransport, AsyncClient
from sensoria.config import Settings
from sensoria.main import create_app
from sensoria.shared.errors import DomainError


@pytest.mark.asyncio
async def test_domain_error_uses_global_handler() -> None:
    test_app = create_app()

    @test_app.get("/__test/domain-error")
    async def raise_domain_error() -> None:
        raise DomainError("TEST_CONFLICT", "Nie można wykonać tej operacji.", 409)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/__test/domain-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "TEST_CONFLICT",
            "message": "Nie można wykonać tej operacji.",
        }
    }


@pytest.mark.asyncio
async def test_http_and_validation_errors_share_the_envelope() -> None:
    test_app = create_app()

    @test_app.get("/__test/validation")
    async def validate_query(count: int) -> dict[str, int]:
        return {"count": count}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        missing = await client.get("/__test/missing")
        invalid = await client.get("/__test/validation", params={"count": "wrong"})

    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "HTTP_404", "message": "Nie znaleziono zasobu."}}
    assert invalid.status_code == 422
    assert invalid.json() == {
        "error": {
            "code": "REQUEST_VALIDATION_ERROR",
            "message": "Żądanie zawiera nieprawidłowe dane.",
        }
    }


@pytest.mark.asyncio
async def test_unexpected_error_hides_technical_details(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/sensoria",  # type: ignore[arg-type]
        ENVIRONMENT="production",
        SECRET_KEY="a-production-test-key-with-more-than-32-characters",  # type: ignore[arg-type]
        _env_file=None,
    )  # type: ignore[call-arg]
    test_app = create_app(settings)

    @test_app.get("/__test/unexpected")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("private database credential detail")

    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/__test/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Wystąpił nieoczekiwany błąd serwera.",
        }
    }
    assert "private database credential detail" not in response.text
    assert "Unhandled server error [RuntimeError]" in caplog.text
    assert "test_errors.py:" in caplog.text
    assert "private database credential detail" not in caplog.text
