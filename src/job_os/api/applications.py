from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.schemas.applications import (
    ApplicationResponse,
    ApprovalResponse,
    CoverLetterResponse,
    ResumeResponse,
)
from job_os.browser.apply_service import BrowserApplyService
from job_os.config import get_settings
from job_os.services.application_service import ApplicationService
from pydantic import BaseModel

router = APIRouter(prefix="/applications", tags=["applications"])


class SubmitApplicationRequest(BaseModel):
    dry_run: bool | None = None
    force: bool = False


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = Query(None),
    approval_status: str | None = Query(None),
    outcome: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationResponse]:
    svc = ApplicationService(session)
    apps = await svc.list_applications(
        status=status, approval_status=approval_status, outcome=outcome, limit=limit, offset=offset
    )
    out: list[ApplicationResponse] = []
    for app in apps:
        job = await svc.get_job_for_application(app.job_id)
        out.append(_app_response(app, job))
    return out


def _app_response(app, job) -> ApplicationResponse:
    meta = app.metadata_ or {}
    return ApplicationResponse(
        id=app.id,
        job_id=app.job_id,
        identity_id=app.identity_id,
        resume_id=app.resume_id,
        cover_letter_id=app.cover_letter_id,
        status=app.status,
        approval_status=app.approval_status,
        applied_at=app.applied_at,
        outcome=app.outcome,
        outcome_at=app.outcome_at,
        rejection_reason=meta.get("rejection_reason") or (app.notes if app.outcome == "rejected" else None),
        notes=app.notes,
        metadata=meta,
        job_title=job.title if job else None,
        company_name=job.company_name if job else None,
        job_url=job.url if job else None,
    )


@router.get("/approvals/pending", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalResponse]:
    svc = ApplicationService(session)
    rows = await svc.list_pending_approvals(limit=limit)
    return [ApprovalResponse.model_validate(r) for r in rows]


class BulkApplyRequest(BaseModel):
    dry_run: bool = True
    approve_pending: bool = True


@router.post("/cleanup")
async def cleanup_applications(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cancel duplicates and non-software applications."""
    app_svc = ApplicationService(session)
    dupes = await app_svc.cancel_duplicate_applications(limit=200)
    cancelled = await app_svc.cancel_non_software_applications(limit=100)
    await session.commit()
    return {"duplicates_cancelled": dupes, "cancelled_irrelevant": cancelled}


@router.post("/approve-all-and-apply")
async def approve_all_and_apply(
    body: BulkApplyRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve all pending drafts, then browser-apply each (dry-run by default)."""
    from job_os.services.workflow_service import WorkflowService

    body = body or BulkApplyRequest()
    app_svc = ApplicationService(session)
    purged = await app_svc.purge_invalid_jobs_and_applications(limit=2000)
    dupes = await app_svc.cancel_duplicate_applications(limit=200)
    cancelled = await app_svc.cancel_non_software_applications(limit=100)
    approved_count = 0
    if body.approve_pending:
        approved = await app_svc.approve_all_pending(limit=50, software_only=True)
        approved_count = len(approved)

    wf_svc = WorkflowService(session)
    workflow = await wf_svc.create_and_run(
        "submit_applications",
        mode="autonomous",
        context={
            "dry_run": body.dry_run,
            "fast_dry_run": body.dry_run,
            "max_apply": 5,
        },
    )
    results = (workflow.context or {}).get("browser_apply_results", [])
    ok = sum(1 for r in results if r.get("success"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = len(results) - ok
    return {
        "approved_count": approved_count,
        "purged_invalid": purged,
        "duplicates_cancelled": dupes,
        "cancelled_irrelevant": cancelled,
        "workflow_id": str(workflow.id),
        "status": workflow.status,
        "apply_results": results,
        "apply_ok": ok,
        "apply_skipped": skipped,
        "apply_failed": failed,
        "dry_run": body.dry_run,
    }


@router.post("/submit-approved")
async def submit_all_approved(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger submit_applications workflow for all approved applications."""
    from job_os.services.workflow_service import WorkflowService

    wf_svc = WorkflowService(session)
    workflow = await wf_svc.run_submit_applications()
    return {"workflow_id": str(workflow.id), "status": workflow.status}


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ApplicationResponse:
    svc = ApplicationService(session)
    app = await svc.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = await svc.get_job_for_application(app.job_id)
    return _app_response(app, job)


@router.post("/{application_id}/submit")
async def submit_application(
    application_id: UUID,
    body: SubmitApplicationRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run Playwright apply. Default dry_run=true (fills form, does not click Submit)."""
    settings = get_settings()
    body = body or SubmitApplicationRequest()
    dry_run = body.dry_run if body.dry_run is not None else settings.browser_dry_run
    svc = BrowserApplyService(session)
    return await svc.apply_application(
        application_id,
        dry_run=dry_run,
        force=body.force,
    )


@router.post("/{application_id}/approve", response_model=ApplicationResponse)
async def approve_application(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ApplicationResponse:
    svc = ApplicationService(session)
    app = await svc.approve_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = await svc.get_job_for_application(app.job_id)
    return _app_response(app, job)


@router.get("/{application_id}/resume", response_model=ResumeResponse)
async def get_application_resume(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ResumeResponse:
    svc = ApplicationService(session)
    app = await svc.get_application(application_id)
    if not app or not app.resume_id:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume = await svc.get_resume(app.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeResponse(
        id=resume.id,
        identity_id=resume.identity_id,
        version=resume.version,
        content_text=resume.content_text,
        content_path=resume.content_path,
        tailored_for_job_id=resume.tailored_for_job_id,
        metadata=resume.metadata_ or {},
    )


@router.get("/{application_id}/cover-letter", response_model=CoverLetterResponse)
async def get_application_cover_letter(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> CoverLetterResponse:
    svc = ApplicationService(session)
    app = await svc.get_application(application_id)
    if not app or not app.cover_letter_id:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    letter = await svc.get_cover_letter(app.cover_letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return CoverLetterResponse(
        id=letter.id,
        job_id=letter.job_id,
        identity_id=letter.identity_id,
        content_text=letter.content_text,
        version=letter.version,
        metadata=letter.metadata_ or {},
    )
