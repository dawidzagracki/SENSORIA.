"""Account subsystem clock seam for deterministic expiry and lockout tests."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC instant; tests can replace this function's module binding."""
    return datetime.now(UTC)
