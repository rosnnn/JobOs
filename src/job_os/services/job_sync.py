"""Fetch new jobs from live boards, filter, and return profile-matched catalog."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from job_os.config import get_settings
from job_os.services.application_service import ApplicationService
from job_os.services.job_catalog import JobCatalogService
from job_os.services.workflow_service import WorkflowService


class JobSyncService:
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _clamp_recent_days(value: int | None) -> int:
        if value is None:
            return 3
        return max(1, min(int(value), 3))

    async def fetch_and_list(
        self,
        *,
        recent_days: int = 3,
        limit: int | None = None,
        purge_invalid: bool = True,
        ui_filters=None,
    ) -> dict:
        """
        Pull fresh postings from RemoteOK, Himalayas, Adzuna, etc.,
        run eligibility + ranking, then return matched jobs for the UI.
        """
        recent_days = self._clamp_recent_days(recent_days)

        wf_svc = WorkflowService(self._session)
        workflow = await wf_svc.create_and_run("discovery_only", mode="autonomous")

        purged = {"jobs_rejected": 0, "applications_cancelled": 0, "location_ineligible_rejected": 0}
        stale = {"jobs_rejected": 0, "applications_cancelled": 0}
        dupes = {"jobs_rejected": 0, "applications_cancelled": 0}
        if purge_invalid:
            app_svc = ApplicationService(self._session)
            purged = await app_svc.purge_invalid_jobs_and_applications(limit=2000)
            loc = await app_svc.purge_location_ineligible_jobs()
            purged["location_ineligible_rejected"] = loc["jobs_rejected"]
            purged["applications_cancelled"] += loc["applications_cancelled"]
            retention_days = max(3, get_settings().job_retention_days)
            stale = await app_svc.purge_stale_jobs(max_age_days=retention_days, limit=5000)
            dupes = await app_svc.purge_duplicate_jobs(limit=8000)
            purged["jobs_rejected"] += stale["jobs_rejected"]
            purged["applications_cancelled"] += stale["applications_cancelled"]
            purged["jobs_rejected"] += dupes["jobs_rejected"]
            purged["applications_cancelled"] += dupes["applications_cancelled"]

        scratch = workflow.context or {}
        discovered = scratch.get("discovered_job_ids") or []
        if not discovered:
            discover_out = scratch.get("discover") or scratch.get("job_discovery") or {}
            if isinstance(discover_out, dict):
                discovered = discover_out.get("job_ids", [])

        discovered_ids: list[UUID] = []
        for raw in discovered:
            try:
                discovered_ids.append(UUID(str(raw)))
            except Exception:
                continue

        catalog = JobCatalogService(self._session)
        fresh_items = await catalog.list_for_profile(
            limit=limit,
            recent_days=recent_days,
            dedupe=True,
            ui_filters=ui_filters,
            include_job_ids=discovered_ids,
        )
        used_cached_catalog = False
        items = fresh_items
        if not items:
            used_cached_catalog = True
            items = await catalog.list_for_profile(
                limit=limit,
                recent_days=recent_days,
                dedupe=True,
                ui_filters=ui_filters,
            )
        discovered_count = len(discovered)
        if not discovered_count and scratch.get("job_count"):
            discovered_count = int(scratch["job_count"])
        by_source = scratch.get("source_counts") or {}
        by_source_status = scratch.get("source_status") or {}

        return {
            "workflow_id": str(workflow.id),
            "workflow_status": workflow.status,
            "discovered_count": discovered_count,
            "by_source": by_source,
            "by_source_status": by_source_status,
            "jobs_for_profile": len(items),
            "fresh_jobs_for_profile": len(fresh_items),
            "used_cached_catalog": used_cached_catalog,
            "purged_invalid": purged,
            "purged_stale": stale,
            "purged_duplicates": dupes,
            "catalog_items": items,
        }
