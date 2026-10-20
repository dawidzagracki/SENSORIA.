"""Administrator login, logout and session introspection."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from sensoria.database import get_session
from sensoria.modules.admin.models import AdminSession

from .auth import (
    NO_STORE,
    AdminPrincipal,
    csrf_digest,
    login_admin,
    logout_admin,
    require_admin_principal,
)

router = APIRouter(prefix="/auth", tags=["admin-auth"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
async def login(
    payload: LoginInput, request: Request, response: Response, session: SessionDependency
) -> dict[str, Any]:
    user, csrf = await login_admin(session, request, response, payload.email, payload.password)
    response.headers.update(NO_STORE)
    return {
        "admin": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
        },
        "csrf_token": csrf,
    }


@router.get("/session")
async def current(
    response: Response,
    session: SessionDependency,
    principal: Annotated[AdminPrincipal, Depends(require_admin_principal)],
) -> dict[str, Any]:
    """Return the identity and a freshly rotated CSRF token (the old one stops working)."""
    csrf = secrets.token_urlsafe(32)
    await session.execute(
        update(AdminSession)
        .where(AdminSession.id == principal.session_id)
        .values(csrf_hash=csrf_digest(csrf))
    )
    await session.commit()
    response.headers.update(NO_STORE)
    return {
        "csrf_token": csrf,
        "admin": {
            "id": str(principal.id),
            "email": principal.email,
            "display_name": principal.display_name,
            "role": principal.role,
        },
    }


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDependency,
    principal: Annotated[AdminPrincipal, Depends(require_admin_principal)],
) -> None:
    await logout_admin(session, principal, response)
