"""Create or reset administrators from the server shell (no default passwords exist)."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from sqlalchemy import select

from sensoria.database import SessionFactory

from .auth import hasher, validate_new_password
from .models import ROLES, AdminUser


async def upsert_admin(email: str, name: str, role: str, password: str) -> str:
    validate_new_password(password)
    async with SessionFactory() as session, session.begin():
        user = await session.scalar(select(AdminUser).where(AdminUser.email == email.lower()))
        encoded = hasher.hash(password)
        if user is None:
            session.add(
                AdminUser(
                    email=email.strip().lower(),
                    display_name=name,
                    password_hash=encoded,
                    role=role,
                )
            )
            return "created"
        user.password_hash, user.role, user.display_name = encoded, role, name
        user.is_active, user.failed_attempts, user.locked_until = True, 0, None
        return "updated"


def main() -> None:
    parser = argparse.ArgumentParser(description="Utwórz lub zaktualizuj administratora.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=ROLES, default="owner")
    args = parser.parse_args()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Hasło: ")
    print(asyncio.run(upsert_admin(args.email, args.name, args.role, password)))


if __name__ == "__main__":
    main()
