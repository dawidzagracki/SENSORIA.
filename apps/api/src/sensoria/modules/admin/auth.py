"""Fail-closed seam for the not-yet-implemented administrator identity provider."""

from dataclasses import dataclass
from uuid import UUID

from sensoria.shared.errors import DomainError


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    """Trusted identity supplied by the future [64] authentication integration."""

    id: UUID


async def require_admin_principal() -> AdminPrincipal:
    """Never infer an administrator from request data or expose admin actions publicly."""
    raise DomainError(
        "ADMIN_AUTH_UNAVAILABLE",
        "Operacje administracyjne są niedostępne do czasu skonfigurowania logowania "
        "administratora.",
        503,
    )
