from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.config import LLMProvider, get_settings
from job_os.core.events import EventService
from job_os.core.llm import LLMClient
from job_os.models.email_message import EmailMessage
from job_os.services.email_service import GmailService
from job_os.services.rejection_analyzer import RejectionAnalyzer
from job_os.services.workflow_service import WorkflowService

router = APIRouter(tags=["email", "analytics"])

VALID_OUTCOMES = {
    "rejected",
    "interview_request",
    "offer",
    "accepted",
    "application_received",
    "job_recommendation",
    "hr_outreach",
    "employer_update",
    "job_related",
    "promotional",
    "sponsorship_ad",
    "security",
    "newsletter",
    "general_notification",
}

GEMINI_RECLASSIFY_BUDGET = 40
GEMINI_RECLASSIFY_TARGETS = {
    "job_recommendation",
    "job_related",
    "general_notification",
    "promotional",
    "newsletter",
}


class EmailMessageResponse(BaseModel):
    id: UUID
    subject: str
    from_address: str
    body_preview: str | None
    received_at: datetime | None
    classified_outcome: str | None
    company_name: str | None
    application_id: UUID | None
    rejection_reason: str | None
    is_walk_in: bool
    is_interview: bool

    model_config = {"from_attributes": True}


class EmailClassification(BaseModel):
    outcome: str
    rejection_reason: str | None = None
    is_walk_in: bool = False
    is_interview: bool = False
    company_name: str | None = None


async def _classify_email_with_gemini(subject: str, body: str, from_address: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    prompt = (
        "Classify this email strictly and conservatively. Use the exact outcome values: rejected, "
        "interview_request, offer, accepted, application_received, job_recommendation, hr_outreach, "
        "employer_update, job_related, promotional, sponsorship_ad, security, newsletter, general_notification.\n"
        "Do not call something a job alert unless it is clearly a recruiting/job-search recommendation.\n"
        "Marketing, admissions, course, newsletter, digest, and promo-style mail should not become job_recommendation.\n"
        "Return JSON only with keys outcome, rejection_reason, is_walk_in, is_interview, company_name.\n\n"
        f"From: {from_address}\n"
        f"Subject: {subject}\n"
        f"Body: {(body or '')[:12000]}"
    )
    llm = LLMClient()
    llm._settings.llm_provider = LLMProvider.GEMINI
    llm._settings.gemini_api_key = settings.gemini_api_key
    try:
        result = await llm.complete_json(
            system="You classify recruiting emails with high precision.",
            user=prompt,
            response_model=EmailClassification,
            temperature=0,
        )
        return result.model_dump()
    except Exception:
        return None


@router.get("/email/messages", response_model=list[EmailMessageResponse])
async def list_email_messages(
    outcome: str | None = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[EmailMessageResponse]:
    stmt = select(EmailMessage).order_by(EmailMessage.received_at.desc().nullslast()).limit(limit)
    if outcome:
        stmt = stmt.where(EmailMessage.classified_outcome == outcome)
    result = await session.execute(stmt)
    return [EmailMessageResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/email/sync")
async def sync_email(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    gmail = GmailService()
    ok, auth_err = gmail.test_connection()
    if not ok:
        return {"status": "failed", "error": auth_err, "synced": 0}

    wf_svc = WorkflowService(session)
    workflow = await wf_svc.create_and_run("email_sync")
    sync_result = (workflow.context or {}).get("email_sync", {})
    error = sync_result.get("error") or workflow.error_message
    await EventService(session).emit(
        event_type="email.sync_completed",
        source="api.email",
        payload={
            "status": workflow.status,
            "synced": sync_result.get("synced", 0),
            "reclassified": sync_result.get("reclassified", 0),
            "updated_apps": sync_result.get("updated_apps", 0),
        },
    )
    return {
        "workflow_id": str(workflow.id),
        "status": workflow.status,
        "synced": sync_result.get("synced", 0),
        "reclassified": sync_result.get("reclassified", 0),
        "updated_apps": sync_result.get("updated_apps", 0),
        "error": error,
        "context": workflow.context,
    }


@router.post("/email/reclassify")
async def reclassify_all_emails(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Re-run classifier on all stored emails (fixes old 'unknown' labels)."""
    gmail = GmailService()
    result = await session.execute(select(EmailMessage))
    rows = list(result.scalars().all())
    counts: dict[str, int] = {}
    failed = 0
    gemini_used = 0

    def _sanitize(raw: dict[str, Any]) -> dict[str, Any]:
        outcome = str(raw.get("outcome") or "general_notification")
        if outcome not in VALID_OUTCOMES:
            outcome = "general_notification"
        company_name = raw.get("company_name")
        if isinstance(company_name, str):
            company_name = company_name.strip()[:500] or None
        else:
            company_name = None
        rejection_reason = raw.get("rejection_reason")
        if isinstance(rejection_reason, str):
            rejection_reason = rejection_reason.strip()[:2000] or None
        else:
            rejection_reason = None
        return {
            "outcome": outcome,
            "company_name": company_name,
            "rejection_reason": rejection_reason,
            "is_walk_in": bool(raw.get("is_walk_in", False)),
            "is_interview": bool(raw.get("is_interview", False)),
        }

    for row in rows:
        try:
            base = gmail.classify(row.subject, row.body_preview or "", row.from_address)
            c = base
            base_outcome = str(base.get("outcome") or "general_notification")
            if gemini_used < GEMINI_RECLASSIFY_BUDGET and base_outcome in GEMINI_RECLASSIFY_TARGETS:
                refined = await _classify_email_with_gemini(row.subject, row.body_preview or "", row.from_address)
                if refined is not None:
                    c = refined
                    gemini_used += 1
            safe = _sanitize(c)
            row.classified_outcome = safe["outcome"]
            row.rejection_reason = safe["rejection_reason"]
            row.is_walk_in = safe["is_walk_in"]
            row.is_interview = safe["is_interview"]
            if safe["company_name"]:
                row.company_name = safe["company_name"]
            counts[safe["outcome"]] = counts.get(safe["outcome"], 0) + 1
        except Exception:
            failed += 1
            continue
    await session.flush()
    await EventService(session).emit(
        event_type="email.reclassified_all",
        source="api.email",
        payload={
            "count": len(rows),
            "failed": failed,
            "gemini_used": gemini_used,
            "by_outcome": counts,
        },
    )
    return {
        "reclassified": len(rows),
        "failed": failed,
        "gemini_used": gemini_used,
        "by_outcome": counts,
    }


@router.get("/email/stats")
async def email_stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    result = await session.execute(select(EmailMessage))
    rows = list(result.scalars().all())
    counts: dict[str, int] = {}
    for row in rows:
        key = row.classified_outcome or "other"
        counts[key] = counts.get(key, 0) + 1
    return {"total": len(rows), "by_outcome": counts}


@router.get("/email/status")
async def email_status() -> dict[str, Any]:
    gmail = GmailService()
    if not gmail.configured:
        return {
            "configured": False,
            "connected": False,
            "address": None,
            "error": "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env",
        }
    ok, err = gmail.test_connection()
    return {
        "configured": True,
        "connected": ok,
        "address": gmail.address,
        "error": err,
    }


@router.get("/analytics/rejections")
async def rejection_analytics(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    analyzer = RejectionAnalyzer(session)
    return await analyzer.analyze()
