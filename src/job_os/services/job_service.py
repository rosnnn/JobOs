from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.job import Job
from job_os.services.job_filters import JobListFilters, matches_ui_filters


class JobService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        source: str | None = None,
        is_remote: bool | None = None,
        offers_sponsorship: bool | None = None,
        fresher_friendly: bool | None = None,
        internship: bool | None = None,
        recent_days: int | None = None,
        keyword: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Job]:
        ui_filters = JobListFilters(
            status=status,
            source=source,
            is_remote=is_remote,
            offers_sponsorship=offers_sponsorship,
            fresher_friendly=fresher_friendly,
            internship=internship,
            keyword=keyword,
        )
        stmt = select(Job).order_by(
            Job.posted_at.desc().nullslast(),
            Job.discovered_at.desc().nullslast(),
            Job.created_at.desc(),
        )
        if status:
            stmt = stmt.where(Job.status == status)
        if source:
            stmt = stmt.where(Job.source == source)
        if recent_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)
            stmt = stmt.where(
                or_(
                    and_(Job.posted_at.is_not(None), Job.posted_at >= cutoff),
                    and_(Job.posted_at.is_(None), Job.discovered_at >= cutoff),
                )
            )
        stmt = stmt.limit(max(limit * 3, 300)).offset(offset)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        filtered = [j for j in rows if matches_ui_filters(j, ui_filters)]
        return filtered[:limit]

    async def get_job(self, job_id: UUID) -> Job | None:
        result = await self._session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()
