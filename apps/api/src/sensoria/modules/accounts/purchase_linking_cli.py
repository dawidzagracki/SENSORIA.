"""Audited repair command for verified guest-purchase ownership links."""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from sensoria.database import SessionFactory

from .clock import utc_now
from .purchase_linking import reconcile_guest_purchases


async def _run(customer_id: UUID, dry_run: bool) -> dict[str, int]:
    async with SessionFactory() as session:
        result = await reconcile_guest_purchases(
            session,
            customer_id,
            source="manual",
            at=utc_now(),
            dry_run=dry_run,
        )
        if not dry_run:
            await session.commit()
        else:
            await session.rollback()
        return result.as_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer-id", required=True, type=UUID)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    result = asyncio.run(_run(arguments.customer_id, arguments.dry_run))
    print(json.dumps({"dry_run": arguments.dry_run, "result": result}, sort_keys=True))


if __name__ == "__main__":
    main()
