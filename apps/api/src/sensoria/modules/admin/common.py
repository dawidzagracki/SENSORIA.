"""Shared admin route helpers: dependencies, pagination and CSV-safe cell escaping."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session

from .auth import AdminPrincipal, require_admin_principal, require_role

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
Staff = Annotated[AdminPrincipal, Depends(require_role("owner", "staff"))]
Owner = Annotated[AdminPrincipal, Depends(require_role("owner"))]
AnyAdmin = Annotated[AdminPrincipal, Depends(require_admin_principal)]
Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def csv_cell(value: object) -> str:
    """Neutralize spreadsheet formula injection (=, +, -, @, tab, CR) in exported cells."""
    text = "" if value is None else str(value)
    if text and text[0] in "=+-@\t\r":
        return "'" + text
    return text
