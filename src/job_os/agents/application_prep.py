from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.models.application import Application
from job_os.config import get_settings
from job_os.models.application import Application
from job_os.browser.apply_url import assess_apply_url
from job_os.services.preferences_service import PreferencesService
from job_os.models.browser import ApprovalRequest
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext


class ApplicationPrepAgent(BaseAgent):
    """Creates draft applications ready for human approval or browser apply."""

    name = "application_prep"
    version = "0.2.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        settings = get_settings()
        tailored = ctx.scratchpad.get("tailored_resumes", [])
        applications: list[dict] = []

        for record in tailored:
            cover_letter_id = record.get("cover_letter_id")
            if not cover_letter_id:
                continue

            job_id = UUID(record["job_id"])
            job = await self._session.get(Job, job_id)
            if not job:
                continue

            prefs = ctx.scratchpad.get("job_preferences") or PreferencesService().load()
            ok, reasons = PreferencesService().matches_job(job, prefs)
            if not ok:
                job.status = "rejected"
                job.reject_reasons = reasons
                continue

            can_auto, _msg = assess_apply_url(job.url, job.source, title=job.title or "")
            if not can_auto:
                job.status = "rejected"
                job.reject_reasons = ["not_auto_applyable_url"]
                continue

            existing = await self._session.execute(
                select(Application).where(
                    Application.job_id == job.id,
                    Application.status != "cancelled",
                )
            )
            if existing.scalar_one_or_none():
                continue

            app = Application(
                job_id=job.id,
                identity_id=UUID(record["identity_id"]),
                resume_id=UUID(record["resume_id"]),
                cover_letter_id=UUID(cover_letter_id),
                status="draft",
                approval_status="pending",
                metadata_={
                    "identity_slug": record.get("identity_slug"),
                    "workflow_id": str(ctx.workflow_id),
                    "ev_score": next(
                        (r.get("ev_score") for r in ctx.scratchpad.get("ranked_jobs", []) if r.get("job_id") == str(job.id)),
                        None,
                    ),
                },
            )
            self._session.add(app)
            await self._session.flush()

            job.status = "application_draft"
            applications.append({
                "application_id": str(app.id),
                "job_id": str(job.id),
                "job_title": job.title,
                "company": job.company_name,
                "resume_id": record["resume_id"],
                "cover_letter_id": cover_letter_id,
            })

            if settings.require_approval_for_apply or settings.is_supervised:
                approval = ApprovalRequest(
                    workflow_id=ctx.workflow_id,
                    step_id=msg.step_id,
                    request_type="application_submit",
                    payload={
                        "application_id": str(app.id),
                        "job_title": job.title,
                        "company": job.company_name,
                        "url": job.url,
                    },
                    status="pending",
                )
                self._session.add(approval)

        await self._session.flush()
        ctx.scratchpad["applications"] = applications

        ctx.scratchpad["application_ids_to_submit"] = [a["application_id"] for a in applications]

        await self._emit(
            ctx,
            msg,
            "application_prep.completed",
            {
                "applications": len(applications),
                "pending_human_approval": settings.require_approval_for_apply,
            },
        )

        return AgentResult(
            success=True,
            output={"applications": applications},
            requires_approval=False,
            next_step_hint="tracking",
        )
