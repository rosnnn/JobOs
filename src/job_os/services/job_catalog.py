"""Profile-matched, deduplicated job catalog for the Jobs UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.job import Job
from job_os.services.job_dedup import job_fingerprint
from job_os.services.job_filters import JobListFilters, location_tier, matches_ui_filters
from job_os.services.job_posted_at import effective_posted_at
from job_os.services.preferences_service import PreferencesService
from job_os.services.job_url_quality import is_real_job_record
from job_os.services.job_role_filter import is_software_engineering_role, normalize_job_title
from job_os.services.list_limits import apply_limit
from job_os.services.profile_service import ProfileService
from job_os.services.resume_match import score_job_match


@dataclass
class CatalogJob:
    job: Job
    match_score: float
    fingerprint: str
    also_on: list[str]
    location_tier: int = 3


class JobCatalogService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_for_profile(
        self,
        *,
        limit: int | None = None,
        recent_days: int | None = 14,
        dedupe: bool = True,
        min_match: float | None = None,
        software_only: bool = True,
        ui_filters: JobListFilters | None = None,
        include_job_ids: list[UUID] | None = None,
    ) -> list[CatalogJob]:
        prefs = PreferencesService().load()
        if recent_days is not None:
            prefs = {**prefs, "recent_days": recent_days}
        prefs_svc = PreferencesService()
        profile = ProfileService().load()
        if min_match is None:
            min_match = float(prefs.get("min_resume_match", 0.08))
        cutoff = None
        if recent_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=recent_days)

        stmt = (
            select(Job)
            .where(Job.status.in_(("discovered", "qualified", "ranked", "application_draft")))
        )
        if include_job_ids is not None:
            if not include_job_ids:
                return []
            stmt = stmt.where(Job.id.in_(include_job_ids))
        if ui_filters and ui_filters.status:
            stmt = stmt.where(Job.status == ui_filters.status)
        if ui_filters and ui_filters.source:
            stmt = stmt.where(Job.source == ui_filters.source)
        stmt = stmt.order_by(
            Job.posted_at.desc().nullslast(),
            Job.discovered_at.desc().nullslast(),
        )
        if cutoff:
            stmt = stmt.where(
                or_(
                    and_(Job.posted_at.is_not(None), Job.posted_at >= cutoff),
                    and_(Job.posted_at.is_(None), Job.discovered_at >= cutoff),
                )
            )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        catalog: list[CatalogJob] = []
        for job in rows:
            real, _ = is_real_job_record(job)
            if not real:
                continue
            ok, _ = prefs_svc.matches_job(job, prefs)
            if not ok:
                continue
            if not matches_ui_filters(job, ui_filters):
                continue
            if software_only and prefs.get("software_only", True):
                role_ok, _ = is_software_engineering_role(
                    normalize_job_title(job.title or ""),
                    job.raw_description,
                )
                if not role_ok:
                    continue
            match = score_job_match(
                title=job.title,
                description=job.raw_description,
                company_name=job.company_name,
                profile=profile,
            )
            if match < min_match:
                continue
            fp = job_fingerprint(job.company_name, job.title)
            tier = location_tier(job, profile)
            catalog.append(
                CatalogJob(
                    job=job,
                    match_score=match,
                    fingerprint=fp,
                    also_on=[job.source],
                    location_tier=tier,
                )
            )

        if not dedupe:
            catalog.sort(
                key=lambda c: (
                    c.location_tier,
                    -effective_posted_at(c.job).timestamp() if effective_posted_at(c.job) else 0,
                    -c.match_score,
                ),
            )
            return apply_limit(catalog, limit)

        by_fp: dict[str, CatalogJob] = {}
        for item in catalog:
            existing = by_fp.get(item.fingerprint)
            if not existing:
                by_fp[item.fingerprint] = item
                continue
            existing.also_on.append(item.job.source)
            newer = effective_posted_at(item.job) > effective_posted_at(existing.job)
            if newer or item.match_score > existing.match_score:
                by_fp[item.fingerprint] = CatalogJob(
                    job=item.job,
                    match_score=max(item.match_score, existing.match_score),
                    fingerprint=item.fingerprint,
                    also_on=sorted(set(existing.also_on + item.also_on)),
                    location_tier=min(existing.location_tier, item.location_tier),
                )
            else:
                by_fp[item.fingerprint].also_on = sorted(
                    set(by_fp[item.fingerprint].also_on + item.also_on)
                )
                by_fp[item.fingerprint].location_tier = min(
                    by_fp[item.fingerprint].location_tier, item.location_tier
                )

        out = list(by_fp.values())
        out.sort(
            key=lambda c: (
                c.location_tier,
                -effective_posted_at(c.job).timestamp() if effective_posted_at(c.job) else 0,
                -c.match_score,
            ),
        )
        return apply_limit(out, limit)
