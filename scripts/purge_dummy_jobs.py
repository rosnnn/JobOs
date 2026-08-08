"""Reject non-real job postings and cancel linked applications."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_os.db.session import AsyncSessionLocal
from job_os.services.application_service import ApplicationService


async def main() -> None:
    async with AsyncSessionLocal() as session:
        svc = ApplicationService(session)
        stats = await svc.purge_invalid_jobs_and_applications(limit=5000)
        await session.commit()
        print(stats)


if __name__ == "__main__":
    asyncio.run(main())
