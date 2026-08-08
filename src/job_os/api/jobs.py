from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.core.events import EventService
from job_os.schemas.jobs import JobResponse
from job_os.services.board_labels import BOARD_LABELS, EMAIL_BOARD_NOTE
from job_os.services.job_catalog import JobCatalogService
from job_os.services.job_filters import JobListFilters
from job_os.services.application_service import ApplicationService
from job_os.services.job_service import JobService
from job_os.services.job_sync import JobSyncService
from job_os.services.workflow_service import WorkflowService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status: str | None = Query(None),
    source: str | None = Query(None),
    is_remote: bool | None = Query(None),
    offers_sponsorship: bool | None = Query(None),
    fresher_friendly: bool | None = Query(None),
    internship: bool | None = Query(None),
    recent_days: int | None = Query(None, ge=1, le=3),
    keyword: str | None = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[JobResponse]:
    svc = JobService(session)
    jobs = await svc.list_jobs(
        status=status,
        source=source,
        is_remote=is_remote,
        offers_sponsorship=offers_sponsorship,
        fresher_friendly=fresher_friendly,
        internship=internship,
        recent_days=recent_days,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return [JobResponse.model_validate(j) for j in jobs]


def _catalog_to_responses(items) -> list[JobResponse]:
    out: list[JobResponse] = []
    for item in items:
        j = item.job
        resp = JobResponse.model_validate(j)
        resp.match_score = item.match_score
        resp.also_on = item.also_on
        resp.board_label = BOARD_LABELS.get(j.source, j.source)
        out.append(resp)
    return out


def _filters_from_query(
    *,
    status: str | None = None,
    source: str | None = None,
    is_remote: bool | None = None,
    offers_sponsorship: bool | None = None,
    fresher_friendly: bool | None = None,
    internship: bool | None = None,
    keyword: str | None = None,
) -> JobListFilters | None:
    f = JobListFilters(
        status=status or None,
        source=source or None,
        is_remote=is_remote,
        offers_sponsorship=offers_sponsorship,
        fresher_friendly=fresher_friendly,
        internship=internship,
        keyword=keyword,
    )
    if not any(
        [
            f.status,
            f.source,
            f.is_remote,
            f.offers_sponsorship,
            f.fresher_friendly,
            f.internship,
            f.keyword,
        ]
    ):
        return None
    return f


@router.get("/recommended", response_model=list[JobResponse])
async def list_recommended_jobs(
    limit: int | None = Query(None, ge=0, description="Optional cap; omit for all profile-matched jobs"),
    recent_days: int = Query(3, ge=1, le=3),
    dedupe: bool = Query(True),
    fetch_live: bool = Query(
        False,
        description="If true, fetch new jobs from boards before listing (same as POST /jobs/sync-live).",
    ),
    status: str | None = Query(None),
    source: str | None = Query(None),
    is_remote: bool | None = Query(None),
    offers_sponsorship: bool | None = Query(None),
    fresher_friendly: bool | None = Query(None),
    internship: bool | None = Query(None),
    keyword: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[JobResponse]:
    """Profile + resume matched jobs. Use fetch_live=true or POST /jobs/sync-live to pull new postings."""
    ui_filters = _filters_from_query(
        status=status,
        source=source,
        is_remote=is_remote,
        offers_sponsorship=offers_sponsorship,
        fresher_friendly=fresher_friendly,
        internship=internship,
        keyword=keyword,
    )
    if fetch_live:
        sync = await JobSyncService(session).fetch_and_list(
            recent_days=recent_days, limit=limit, ui_filters=ui_filters
        )
        await session.commit()
        return _catalog_to_responses(sync["catalog_items"])

    catalog = JobCatalogService(session)
    items = await catalog.list_for_profile(
        limit=limit,
        recent_days=recent_days,
        dedupe=dedupe,
        ui_filters=ui_filters,
    )
    return _catalog_to_responses(items)


async def _run_live_sync(
    session: AsyncSession,
    *,
    recent_days: int,
    limit: int | None,
    ui_filters: JobListFilters | None = None,
) -> dict:
    try:
        sync = await JobSyncService(session).fetch_and_list(
            recent_days=recent_days, limit=limit, ui_filters=ui_filters
        )
        await session.commit()
        jobs = _catalog_to_responses(sync["catalog_items"])
        purged = sync.get("purged_invalid") or {}
        stale = sync.get("purged_stale") or {"jobs_rejected": 0}
        dupes = sync.get("purged_duplicates") or {"jobs_rejected": 0}
        by_source = sync.get("by_source") or {}
        by_source_status = sync.get("by_source_status") or {}
        used_cached_catalog = bool(sync.get("used_cached_catalog"))
        fresh_jobs_for_profile = int(sync.get("fresh_jobs_for_profile") or 0)
        source_label = "cached recent catalog" if used_cached_catalog else "current sync"
        return {
            "workflow_id": sync["workflow_id"],
            "workflow_status": sync["workflow_status"],
            "discovered_count": sync["discovered_count"],
            "by_source": by_source,
            "by_source_status": by_source_status,
            "jobs_for_profile": sync["jobs_for_profile"],
            "purged_invalid": purged,
            "purged_duplicates": dupes,
            "jobs": jobs,
            "message": (
                f"Fetched live from job boards - {len(jobs)} roles match your profile from {source_label}. "
                f"Fresh matches this run: {fresh_jobs_for_profile}. "
                f"Cleanup: {purged.get('jobs_rejected', 0)} rejected, "
                f"{stale.get('jobs_rejected', 0)} stale removed, "
                f"{dupes.get('jobs_rejected', 0)} duplicates removed."
            ),
        }
    except Exception as exc:
        catalog = JobCatalogService(session)
        items = await catalog.list_for_profile(
            limit=limit,
            recent_days=recent_days,
            dedupe=True,
            ui_filters=ui_filters,
        )
        return {
            "workflow_id": None,
            "workflow_status": "degraded",
            "discovered_count": 0,
            "jobs_for_profile": len(items),
            "purged_invalid": {"jobs_rejected": 0, "applications_cancelled": 0},
            "jobs": _catalog_to_responses(items),
            "message": f"Board sync degraded to cached catalog: {exc}",
        }


@router.get("/sync-live")
@router.post("/sync-live")
async def sync_live_jobs(
    recent_days: int = Query(3, ge=1, le=3),
    limit: int | None = Query(None, ge=0, description="Optional cap; omit for all profile-matched jobs"),
    status: str | None = Query(None),
    source: str | None = Query(None),
    is_remote: bool | None = Query(None),
    offers_sponsorship: bool | None = Query(None),
    fresher_friendly: bool | None = Query(None),
    internship: bool | None = Query(None),
    keyword: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fetch new jobs from all enabled boards, filter to your profile, return list."""
    ui_filters = _filters_from_query(
        status=status,
        source=source,
        is_remote=is_remote,
        offers_sponsorship=offers_sponsorship,
        fresher_friendly=fresher_friendly,
        internship=internship,
        keyword=keyword,
    )
    result = await _run_live_sync(session, recent_days=recent_days, limit=limit, ui_filters=ui_filters)
    await EventService(session).emit(
        event_type="jobs.live_sync_completed",
        source="api.jobs",
        payload={
            "workflow_status": result.get("workflow_status"),
            "discovered_count": result.get("discovered_count", 0),
            "by_source": result.get("by_source", {}),
            "by_source_status": result.get("by_source_status", {}),
            "jobs_for_profile": result.get("jobs_for_profile", 0),
            "purged_duplicates": (result.get("purged_duplicates") or {}).get("jobs_rejected", 0),
            "message": result.get("message"),
        },
    )
    await session.commit()
    return result


@router.post("/purge-invalid")
async def purge_invalid_jobs(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove listing-page / scraped junk jobs and cancel their applications."""
    app_svc = ApplicationService(session)
    stats = await app_svc.purge_invalid_jobs_and_applications(limit=2000)
    await EventService(session).emit(
        event_type="jobs.invalid_purged",
        source="api.jobs",
        payload=stats,
    )
    await session.commit()
    return {
        "message": "Invalid jobs rejected and linked applications cancelled.",
        **stats,
    }


@router.post("/discover-global")
async def discover_global_jobs(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fetch from all enabled global/India boards, then filter & rank."""
    wf_svc = WorkflowService(session)
    sync = await JobSyncService(session).fetch_and_list(recent_days=3, limit=None)
    await session.commit()
    return {
        "workflow_id": sync["workflow_id"],
        "status": sync["workflow_status"],
        "message": EMAIL_BOARD_NOTE,
        "sources": list(BOARD_LABELS.keys()),
        "jobs_for_profile": sync["jobs_for_profile"],
        "discovered_count": sync["discovered_count"],
        "purged_invalid": sync["purged_invalid"],
    }


@router.get("/boards")
async def list_job_boards() -> dict:
    return {"boards": BOARD_LABELS, "email_note": EMAIL_BOARD_NOTE}


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    svc = JobService(session)
    job = await svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)
