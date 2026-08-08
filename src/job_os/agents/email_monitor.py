from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.config import LLMProvider
from job_os.core.llm import LLMClient
from job_os.models.application import Application
from job_os.models.email_message import EmailMessage
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.services.email_service import EmailAuthError, GmailService
from job_os.services.credentials_service import CredentialsService


class EmailMonitorAgent(BaseAgent):
    name = "email_monitor"
    version = "0.2.0"

    async def _classify_with_gemini(self, parsed) -> dict | None:
        creds = CredentialsService().load()
        gemini_key = creds.get("gemini_api_key")
        if not gemini_key:
            return None

        from pydantic import BaseModel

        class Out(BaseModel):
            outcome: str
            rejection_reason: str | None = None
            is_walk_in: bool = False
            is_interview: bool = False
            company_name: str | None = None

        prompt = (
            "Classify this recruiting email into exactly one outcome: rejected, interview_request, offer, "
            "accepted, application_received, job_recommendation, hr_outreach, employer_update, job_related, "
            "promotional, sponsorship_ad, security, newsletter, general_notification.\n"
            "Treat newsletter, marketing, platform promos, and non-job ads as promotional unless it is a true hiring mail.\n"
            "Return strict JSON only with keys outcome, rejection_reason, is_walk_in, is_interview, company_name.\n\n"
            f"From: {parsed.from_address}\n"
            f"Subject: {parsed.subject}\n"
            f"Body: {(parsed.body_preview or '')[:7000]}"
        )
        try:
            llm = LLMClient()
            llm._settings.llm_provider = LLMProvider.GEMINI
            llm._settings.gemini_api_key = gemini_key  # runtime fallback for this classification call
            refined = await llm.complete_json(
                system="You classify recruiting emails with high precision.",
                user=prompt,
                response_model=Out,
                temperature=0,
            )
            return refined.model_dump()
        except Exception:
            return None

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        gmail = GmailService()
        if not gmail.configured:
            return AgentResult(
                success=True,
                output={"synced": 0, "message": "gmail_not_configured"},
                next_step_hint="tracking",
            )

        try:
            emails = gmail.fetch_recent(limit=200)
        except EmailAuthError as exc:
            ctx.scratchpad["email_sync"] = {"synced": 0, "error": str(exc)}
            return AgentResult(
                success=False,
                output={"synced": 0, "error": str(exc)},
                error_detail=str(exc),
                next_step_hint="tracking",
            )

        synced = 0
        updated = 0
        reclassified = 0
        updated_apps = 0
        use_gemini = bool(CredentialsService().load().get("gemini_api_key"))

        for parsed in emails:
            classification = await self._classify_with_gemini(parsed) if use_gemini else None
            if classification is None:
                classification = gmail.classify(parsed.subject, parsed.body_preview, parsed.from_address)

            existing = await self._session.execute(
                select(EmailMessage).where(EmailMessage.message_id == parsed.message_id)
            )
            record = existing.scalar_one_or_none()

            if record:
                record.classified_outcome = classification["outcome"]
                record.rejection_reason = classification.get("rejection_reason")
                record.is_walk_in = classification.get("is_walk_in", False)
                record.is_interview = classification.get("is_interview", False)
                if classification.get("company_name"):
                    record.company_name = classification["company_name"]
                reclassified += 1
            else:
                app_id = await self._match_application(
                    classification.get("company_name"), parsed
                )
                record = EmailMessage(
                    message_id=parsed.message_id,
                    subject=parsed.subject,
                    from_address=parsed.from_address,
                    body_preview=parsed.body_preview,
                    received_at=parsed.received_at,
                    classified_outcome=classification["outcome"],
                    company_name=classification.get("company_name"),
                    application_id=app_id,
                    rejection_reason=classification.get("rejection_reason"),
                    is_walk_in=classification.get("is_walk_in", False),
                    is_interview=classification.get("is_interview", False),
                    raw_headers=parsed.raw_headers,
                )
                self._session.add(record)
                synced += 1

                if app_id and classification["outcome"] in (
                    "rejected",
                    "interview_request",
                    "offer",
                    "accepted",
                    "application_received",
                ):
                    app = await self._session.get(Application, app_id)
                    if app:
                        outcome_map = {
                            "application_received": None,
                            "interview_request": "interview_request",
                        }
                        mapped = outcome_map.get(classification["outcome"], classification["outcome"])
                        if mapped:
                            app.outcome = mapped
                            app.outcome_at = datetime.now(timezone.utc)
                        if classification.get("rejection_reason"):
                            app.notes = classification["rejection_reason"]
                            app.metadata_ = {
                                **(app.metadata_ or {}),
                                "rejection_reason": classification["rejection_reason"],
                            }
                        if classification.get("is_walk_in"):
                            app.metadata_ = {**(app.metadata_ or {}), "walk_in": True}
                        updated_apps += 1

            updated += 1

        await self._session.flush()
        ctx.scratchpad["email_sync"] = {
            "synced": synced,
            "reclassified": reclassified,
            "updated_apps": updated_apps,
        }

        await self._emit(
            ctx,
            msg,
            "email_monitor.completed",
            {"synced": synced, "reclassified": reclassified, "updated_apps": updated_apps},
        )

        return AgentResult(
            success=True,
            output={
                "synced": synced,
                "reclassified": reclassified,
                "updated_apps": updated_apps,
            },
            next_step_hint="rejection_analysis",
        )

    async def _match_application(self, company: str | None, parsed) -> UUID | None:
        stmt = select(Application).order_by(Application.created_at.desc()).limit(200)
        result = await self._session.execute(stmt)
        company_lower = (company or "").lower()
        subject_l = (parsed.subject or "").lower()
        from_l = (parsed.from_address or "").lower()

        for app in result.scalars().all():
            meta = app.metadata_ or {}
            applied_co = (meta.get("applied_company") or "").lower()
            if applied_co and (applied_co in company_lower or company_lower in applied_co):
                return app.id
            if applied_co and applied_co in subject_l:
                return app.id
            job = await self._session.get(Job, app.job_id)
            if not job:
                continue
            jco = (job.company_name or "").lower()
            if company_lower and jco and (company_lower in jco or jco in company_lower):
                return app.id
            if jco and jco in subject_l:
                return app.id
            if jco and jco.split()[0] in from_l:
                return app.id
        return None
