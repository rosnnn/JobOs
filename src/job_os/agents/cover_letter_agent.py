from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.config import get_settings
from job_os.models.identity import CoverLetter, ProfessionalIdentity, Resume
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.services.cover_letter_builder import CoverLetterBuilder
from job_os.services.profile_service import ProfileService


class CoverLetterAgent(BaseAgent):
    name = "cover_letter"
    version = "0.2.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        settings = get_settings()
        profile = ctx.user_profile or ProfileService().load()
        tailored = ctx.scratchpad.get("tailored_resumes", [])

        if not tailored:
            return AgentResult(success=True, output={"cover_letters": 0})

        builder = CoverLetterBuilder()
        letters: list[dict] = []
        errors: list[str] = []

        for record in tailored:
            job_id = UUID(record["job_id"])
            resume_id = UUID(record["resume_id"])

            job = await self._session.get(Job, job_id)
            resume = await self._session.get(Resume, resume_id)
            if not job or not resume:
                continue

            identity = await self._session.get(ProfessionalIdentity, resume.identity_id)
            if not identity:
                continue

            try:
                result = await builder.generate(
                    profile=profile,
                    identity=identity,
                    job=job,
                    resume_excerpt=resume.content_text or "",
                    use_llm=settings.enable_llm_tailoring,
                )
            except Exception as exc:
                errors.append(f"{job_id}:{exc}")
                continue

            letter = CoverLetter(
                job_id=job.id,
                identity_id=identity.id,
                content_text=result.content_text,
                metadata_={
                    "method": result.method,
                    "resume_id": str(resume.id),
                    "workflow_id": str(ctx.workflow_id),
                },
            )
            self._session.add(letter)
            await self._session.flush()

            record["cover_letter_id"] = str(letter.id)
            letters.append({
                "job_id": str(job.id),
                "cover_letter_id": str(letter.id),
                "resume_id": str(resume.id),
                "method": result.method,
            })

        ctx.scratchpad["tailored_resumes"] = tailored
        ctx.scratchpad["cover_letters"] = letters

        await self._emit(
            ctx,
            msg,
            "cover_letter.completed",
            {"count": len(letters), "errors": errors},
        )

        return AgentResult(
            success=True,
            output={"cover_letters": len(letters), "records": letters, "errors": errors},
            next_step_hint="application_prep",
        )
