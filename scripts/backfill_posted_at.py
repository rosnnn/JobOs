"""Backfill jobs.posted_at from parsed_metadata for existing rows."""
import asyncio

from sqlalchemy import select

from job_os.db.session import AsyncSessionLocal
from job_os.models.job import Job
from job_os.services.job_posted_at import parse_posted_at


async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.posted_at.is_(None)))
        updated = 0
        for job in result.scalars():
            posted = parse_posted_at(job.parsed_metadata)
            if not posted:
                posted = job.discovered_at
            if posted:
                job.posted_at = posted
                updated += 1
        await session.commit()
        print(f"backfilled posted_at on {updated} jobs")


if __name__ == "__main__":
    asyncio.run(main())
