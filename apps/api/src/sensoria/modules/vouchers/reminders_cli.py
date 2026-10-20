"""Run one bounded voucher-reminder qualification pass from cron or manually."""

import asyncio
import json

from .reminders import run_voucher_reminders


async def main() -> None:
    result = await run_voucher_reminders()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
