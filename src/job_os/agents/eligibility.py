import re
from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.core.safety import SafetyValidator
from job_os.services.preferences_service import PreferencesService
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.schemas.jobs import JobEligibilityResult, JobIngest

POSITIVE_SIGNALS = [
    (r"\bvisa sponsorship\b", "sponsorship_mentioned", 0.25),
    (r"\bsponsor\b", "sponsor_keyword", 0.1),
    (r"\brelocate\b", "relocation", 0.1),
    (r"\bintern(ship)?\b", "intern_friendly", 0.2),
    (r"\bapprentice\b", "apprentice", 0.15),
    (r"\bnew grad\b", "new_grad", 0.2),
    (r"\bjunior\b", "junior", 0.15),
    (r"\bentry[- ]?level\b", "entry_level", 0.15),
    (r"\bgraduate\b", "graduate", 0.15),
    (r"\b0[- ]?2 years\b", "fresher_years", 0.2),
    (r"\bremote\b", "remote", 0.1),
    (r"\bglobal\b", "global", 0.05),
]

NEGATIVE_SIGNALS = [
    (r"\b5\+ years\b", "senior_years", -0.2),
    (r"\b10\+ years\b", "very_senior", -0.4),
    (r"\bprincipal\b", "principal", -0.15),
    (r"\bstaff engineer\b", "staff", -0.15),
]


class EligibilityAgent(BaseAgent):
    name = "eligibility"
    version = "0.1.0"

    def __init__(self, session, events):
        super().__init__(session, events)
        self._safety = SafetyValidator()
        self._prefs = PreferencesService()

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        job_ids = [UUID(jid) for jid in ctx.scratchpad.get("discovered_job_ids", [])]
        if not job_ids and msg.payload.get("job_ids"):
            job_ids = [UUID(j) for j in msg.payload["job_ids"]]

        stmt = select(Job).where(Job.id.in_(job_ids)) if job_ids else select(Job).where(Job.status == "discovered").limit(100)
        result = await self._session.execute(stmt)
        jobs = list(result.scalars().all())

        prefs = self._prefs.load()
        if ctx.scratchpad.get("job_preferences"):
            prefs = {**prefs, **ctx.scratchpad["job_preferences"]}

        qualified: list[JobEligibilityResult] = []
        rejected: list[JobEligibilityResult] = []

        for job in jobs:
            ingest = JobIngest(
                external_id=job.external_id,
                source=job.source,
                title=job.title,
                url=job.url,
                company_name=job.company_name,
                location=job.location,
                raw_description=job.raw_description or "",
                metadata=job.parsed_metadata or {},
            )
            verdict = self._safety.check_job_eligibility_hard(ingest)
            score, flags = self._score_soft(ingest)

            if not verdict.allowed:
                elig = JobEligibilityResult(
                    job_id=job.id,
                    external_id=job.external_id,
                    eligible=False,
                    eligibility_score=0.0,
                    flags=flags,
                    reject_reasons=verdict.violations,
                )
                rejected.append(elig)
                job.status = "rejected"
                job.reject_reasons = verdict.violations
                job.eligibility_score = 0.0
            else:
                final_score = max(0.0, min(1.0, score))
                pref_match, pref_reasons = self._prefs.matches_job(job, prefs)
                eligible = final_score >= 0.35 and pref_match
                reject_list: list[str] = []
                if not pref_match:
                    reject_list.extend(pref_reasons)
                if final_score < 0.35:
                    reject_list.append("low_eligibility_score")
                elig = JobEligibilityResult(
                    job_id=job.id,
                    external_id=job.external_id,
                    eligible=eligible,
                    eligibility_score=final_score,
                    flags=flags,
                    reject_reasons=reject_list if not eligible else [],
                )
                if eligible:
                    qualified.append(elig)
                    job.status = "qualified"
                    job.eligibility_score = final_score
                    job.is_remote = flags.get("remote", job.is_remote)
                    # None = unknown; True only when sponsor/visa mentioned
                    job.offers_sponsorship = True if flags.get("sponsorship") else None
                    job.fresher_friendly = flags.get("fresher", None)
                else:
                    rejected.append(elig)
                    job.status = "rejected"
                    job.reject_reasons = elig.reject_reasons
                    job.eligibility_score = final_score

        await self._session.flush()
        ctx.scratchpad["qualified_job_ids"] = [str(q.job_id) for q in qualified if q.job_id]

        await self._emit(
            ctx,
            msg,
            "eligibility.completed",
            {"qualified": len(qualified), "rejected": len(rejected)},
        )

        return AgentResult(
            success=True,
            output={
                "qualified_count": len(qualified),
                "rejected_count": len(rejected),
                "qualified_job_ids": ctx.scratchpad["qualified_job_ids"],
            },
            next_step_hint="strategy",
        )

    def _score_soft(self, job: JobIngest) -> tuple[float, dict[str, bool]]:
        text = f"{job.title} {job.raw_description or ''} {job.location or ''}".lower()
        score = 0.5  # base for recent graduate with internship experience
        flags: dict[str, bool] = {
            "remote": bool(re.search(r"\bremote\b", text)),
            "sponsorship": bool(re.search(r"sponsor|visa", text)),
            "fresher": False,
            "internship": bool(re.search(r"\bintern(ship)?\b|\bapprentice\b|\bnew grad\b", text, re.I)),
        }

        for pattern, _name, delta in POSITIVE_SIGNALS:
            if re.search(pattern, text, re.I):
                score += delta
                if "junior" in pattern or "entry" in pattern or "intern" in pattern or "graduate" in pattern or "fresher" in pattern:
                    flags["fresher"] = True

        for pattern, _name, delta in NEGATIVE_SIGNALS:
            if re.search(pattern, text, re.I):
                score += delta

        if job.metadata.get("is_remote"):
            flags["remote"] = True
            score += 0.1

        return score, flags
