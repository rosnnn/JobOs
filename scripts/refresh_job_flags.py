"""Fix offers_sponsorship flags and show catalog size."""
import asyncio

from sqlalchemy import select, update

from job_os.db.session import AsyncSessionLocal
from job_os.models.job import Job
from job_os.services.job_catalog import JobCatalogService


async def main():
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Job)
            .where(Job.offers_sponsorship.is_(False))
            .values(offers_sponsorship=None)
        )
        await session.commit()

        catalog = JobCatalogService(session)
        items = await catalog.list_for_profile(limit=None, recent_days=14)
        print(f"catalog jobs after fix: {len(items)}")
        for item in items[:15]:
            j = item.job
            print(f"  {item.match_score:.0%} | {j.source} | {j.title[:55]}")


if __name__ == "__main__":
    asyncio.run(main())
