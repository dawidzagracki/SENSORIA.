"""Application startup and documentation route tests."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sensoria.config import Settings
from sensoria.main import create_app

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_docs_and_openapi_are_available(api_client: AsyncClient) -> None:
    docs_response = await api_client.get("/docs")
    openapi_response = await api_client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert "text/html" in docs_response.headers["content-type"]
    assert openapi_response.status_code == 200
    assert openapi_response.json()["info"]["version"] == "0.2.0"
    assert "/health" in openapi_response.json()["paths"]


@pytest.mark.asyncio
async def test_production_disables_all_api_documentation() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/sensoria",  # type: ignore[arg-type]
        ENVIRONMENT="production",
        SECRET_KEY="a-production-test-key-with-more-than-32-characters",  # type: ignore[arg-type]
        _env_file=None,
    )  # type: ignore[call-arg]
    test_app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        responses = [await client.get(path) for path in ("/docs", "/redoc", "/openapi.json")]

    assert [response.status_code for response in responses] == [404, 404, 404]


def test_application_fails_without_database_url_and_does_not_print_secret() -> None:
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    environment.pop("TEST_DATABASE_URL", None)
    environment["ENVIRONMENT"] = "development"
    environment["SENSORIA_ENV_FILE"] = str(API_ROOT / ".missing-settings-test.env")
    secret_sentinel = "must-never-appear-in-settings-errors"
    environment["SECRET_KEY"] = secret_sentinel
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(API_ROOT / "src"), environment.get("PYTHONPATH")])
    )

    result = subprocess.run(
        [sys.executable, "-c", "import sensoria.main"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "DATABASE_URL" in output
    assert "Brak wymaganej zmiennej środowiskowej" in output
    assert secret_sentinel not in output


@pytest.mark.parametrize(
    ("values", "expected_name", "forbidden"),
    [
        (
            {
                "DATABASE_URL": "postgresql://user:db-password-sentinel@localhost/sensoria",
                "ENVIRONMENT": "development",
                "SECRET_KEY": "ordinary-development-placeholder",
            },
            "DATABASE_URL",
            "db-password-sentinel",
        ),
        (
            {
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/sensoria",
                "ENVIRONMENT": "test",
                "SECRET_KEY": "secret-sentinel-for-environment",
            },
            "ENVIRONMENT",
            "secret-sentinel-for-environment",
        ),
        (
            {
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/sensoria",
                "ENVIRONMENT": "production",
                "SECRET_KEY": "short-secret-sentinel",
            },
            "SECRET_KEY",
            "short-secret-sentinel",
        ),
    ],
)
def test_invalid_configuration_fails_safely(
    values: dict[str, str], expected_name: str, forbidden: str
) -> None:
    environment = os.environ.copy()
    environment.pop("TEST_DATABASE_URL", None)
    environment.update(values)
    environment["SENSORIA_ENV_FILE"] = str(API_ROOT / ".missing-settings-test.env")
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(API_ROOT / "src"), environment.get("PYTHONPATH")])
    )

    result = subprocess.run(
        [sys.executable, "-c", "import sensoria.main"],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert expected_name in output
    assert forbidden not in output
