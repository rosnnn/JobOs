from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.config import get_settings
from job_os.core.llm import LLMClient
from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.schemas.jobs import JobRanked
from job_os.strategy.engine import StrategyEngine
from job_os.world_model.service import WorldModelService


class StrategyAgent(BaseAgent):
    name = "strategy"
    version = "0.1.0"

    async def _llm_fit_score(self, *, job: Job, profile: dict | None) -> float | None:
        settings = get_settings()
        has_key = bool(settings.openai_api_key or settings.anthropic_api_key or settings.gemini_api_key)
        if not has_key:
            return None

        class FitScore(BaseModel):
            fit_score: float

        profile_skills = ", ".join((profile or {}).get("skills", [])[:20])
        user = (
            "Return strict JSON {\"fit_score\": number_between_0_and_1}. "
            "Score how relevant this role is for the candidate profile. "
            f"Title: {job.title}\n"
            f"Company: {job.company_name or ''}\n"
            f"Location: {job.location or ''}\n"
            f"Description: {(job.raw_description or '')[:2500]}\n"
            f"Candidate skills: {profile_skills}"
        )
        try:
            res = await LLMClient().complete_json(
                system=(
                    "You are a strict job-fit scorer. "
                    "Favor software roles, fresher-friendly opportunities, and strong skill overlap."
                ),
                user=user,
                response_model=FitScore,
                temperature=0,
            )
            return max(0.0, min(1.0, float(res.fit_score)))
        except Exception:
            return None

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        world_svc = WorldModelService(self._session)
        world = await world_svc.get_current()
        ctx.world_state = world

        job_ids = [UUID(j) for j in ctx.scratchpad.get("qualified_job_ids", [])]
        stmt = select(Job).where(Job.id.in_(job_ids)) if job_ids else select(Job).where(Job.status == "qualified")
        result = await self._session.execute(stmt)
        jobs = list(result.scalars().all())

        id_result = await self._session.execute(
            select(ProfessionalIdentity).where(ProfessionalIdentity.is_active.is_(True))
        )
        identities = list(id_result.scalars().all())

        engine = StrategyEngine(world_state=world, identities=identities)
        ranked: list[JobRanked] = []
        profile = ctx.user_profile or {}
        llm_budget = 30

        for job in jobs:
            ev, identity_slug, rationale = engine.score_job(job)
            if llm_budget > 0:
                llm_fit = await self._llm_fit_score(job=job, profile=profile)
                if llm_fit is not None:
                    ev = (ev * 0.85) + (llm_fit * 0.15)
                llm_budget -= 1
            job.strategy_score = ev
            job.status = "ranked"
            ranked.append(
                JobRanked(
                    job_id=job.id,
                    ev_score=ev,
                    recommended_identity_slug=identity_slug,
                    rationale=rationale,
                )
            )

        ranked.sort(key=lambda r: r.ev_score, reverse=True)
        await self._session.flush()

        top = ranked[:20]
        ctx.scratchpad["ranked_jobs"] = [r.model_dump(mode="json") for r in top]

        await self._emit(
            ctx,
            msg,
            "strategy.ranked",
            {"count": len(ranked), "top_ev": top[0].ev_score if top else 0},
        )

        return AgentResult(
            success=True,
            output={"ranked_jobs": [r.model_dump(mode="json") for r in top]},
            next_step_hint="resume_tailoring",
        )
