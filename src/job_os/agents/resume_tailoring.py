from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.config import get_settings
from job_os.models.identity import ProfessionalIdentity, Resume
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.services.profile_service import ProfileService
from job_os.services.resume_builder import ResumeBuilder


class ResumeTailoringAgent(BaseAgent):
    name = "resume_tailoring"
    version = "0.2.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        settings = get_settings()
        profile = ProfileService().load()
        ctx.user_profile = profile

        ranked = ctx.scratchpad.get("ranked_jobs", [])[: settings.max_tailor_per_run]
        if not ranked:
            return AgentResult(success=True, output={"tailored": 0, "resume_ids": []})

        builder = ResumeBuilder()
        tailored_records: list[dict] = []
        errors: list[str] = []

        for item in ranked:
            job_id = UUID(item["job_id"])
            identity_slug = item.get("recommended_identity_slug")

            job = await self._session.get(Job, job_id)
            if not job:
                continue

            identity = await self._resolve_identity(identity_slug)
            if not identity:
                errors.append(f"no_identity:{job_id}")
                continue

            try:
                result = await builder.tailor(
                    profile=profile,
                    identity=identity,
                    job=job,
                    use_llm=settings.enable_llm_tailoring,
                )
            except Exception as exc:
                errors.append(f"{job_id}:{exc}")
                continue

            content_path = await self._save_resume_file(job_id, identity.slug, result.content_text)

            resume = Resume(
                identity_id=identity.id,
                content_text=result.content_text,
                content_path=str(content_path),
                tailored_for_job_id=job.id,
                metadata_={
                    "method": result.method,
                    "keywords_injected": result.keywords_injected,
                    "workflow_id": str(ctx.workflow_id),
                },
            )
            self._session.add(resume)
            await self._session.flush()

            tailored_records.append({
                "job_id": str(job.id),
                "resume_id": str(resume.id),
                "identity_id": str(identity.id),
                "identity_slug": identity.slug,
                "method": result.method,
            })

        ctx.scratchpad["tailored_resumes"] = tailored_records

        await self._emit(
            ctx,
            msg,
            "resume_tailoring.completed",
            {"tailored": len(tailored_records), "errors": errors},
        )

        return AgentResult(
            success=True,
            output={"tailored": len(tailored_records), "records": tailored_records, "errors": errors},
            next_step_hint="cover_letter",
        )

    async def _resolve_identity(self, slug: str | None) -> ProfessionalIdentity | None:
        if slug:
            result = await self._session.execute(
                select(ProfessionalIdentity).where(ProfessionalIdentity.slug == slug)
            )
            identity = result.scalar_one_or_none()
            if identity:
                return identity
        result = await self._session.execute(
            select(ProfessionalIdentity).where(ProfessionalIdentity.is_active.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    async def _save_resume_file(self, job_id: UUID, identity_slug: str, content: str) -> Path:
        settings = get_settings()
        out_dir = Path(settings.artifact_path) / "resumes" / str(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{identity_slug}.md"
        path.write_text(content, encoding="utf-8")
        return path
