"""Cover letter generation with truth constraints."""

from typing import Any

from pydantic import BaseModel, Field

from job_os.core.llm import LLMClient
from job_os.core.truth import TruthValidator
from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job


class CoverLetterOutput(BaseModel):
    content_text: str
    method: str = "template"


class CoverLetterBuilder:
    def __init__(self) -> None:
        self._truth = TruthValidator()
        self._llm: LLMClient | None = None

    async def generate(
        self,
        *,
        profile: dict[str, Any],
        identity: ProfessionalIdentity,
        job: Job,
        resume_excerpt: str,
        use_llm: bool = False,
    ) -> CoverLetterOutput:
        content = self._template_letter(profile, identity, job)

        if use_llm and self._has_llm_key():
            try:
                content = await self._generate_with_llm(profile, identity, job, resume_excerpt)
                method = "llm"
            except Exception:
                method = "template"
        else:
            method = "template"

        check = self._truth.validate_document(content, profile, document_type="cover_letter")
        if not check.valid:
            content = self._template_letter(profile, identity, job)
            method = "template_fallback"

        return CoverLetterOutput(content_text=content, method=method)

    def _has_llm_key(self) -> bool:
        from job_os.config import get_settings

        s = get_settings()
        return bool(s.openai_api_key or s.anthropic_api_key or s.gemini_api_key)

    def _template_letter(
        self,
        profile: dict,
        identity: ProfessionalIdentity,
        job: Job,
    ) -> str:
        name = profile.get("full_name", "Candidate")
        company = job.company_name or "your company"
        auth = profile.get("work_authorization", {})

        sponsorship_para = ""
        if auth.get("requires_sponsorship"):
            sponsorship_para = (
                "I am based in India and would require visa sponsorship to work in your country. "
                "I am fully committed to relocating and contributing long-term if given the opportunity.\n\n"
            )

        top_project = (profile.get("projects") or [{}])[0]
        project_ref = top_project.get("name", "a recent software project")

        tone = identity.tone or "professional"
        opening = "Dear Hiring Manager," if tone == "professional" else "Hello,"

        return f"""{opening}

I am writing to apply for the {job.title} position at {company}. As an entry-level {identity.role_focus} \
with hands-on experience from {project_ref}, I am excited about the opportunity to contribute to your team.

My background includes: {', '.join(profile.get('skills', [])[:6])}. \
I have built projects demonstrating practical ability in {', '.join((identity.ats_keywords or [])[:4])}, \
which align closely with this role.

{sponsorship_para}I would welcome the chance to discuss how my skills and enthusiasm can support {company}'s goals.

Sincerely,
{name}
{profile.get('email', '')}
{profile.get('phone', '')}
""".strip()

    async def _generate_with_llm(
        self,
        profile: dict,
        identity: ProfessionalIdentity,
        job: Job,
        resume_excerpt: str,
    ) -> str:
        import json

        system = (
            "Write a concise cover letter (250-350 words). RULES:\n"
            "1. Only use facts from canonical_profile.\n"
            "2. Never fabricate experience or authorization status.\n"
            "3. If requires_sponsorship is true, clearly state sponsorship need.\n"
            "4. Match tone to identity.tone.\n"
            'Respond JSON: {"content_text": "..."}'
        )
        user = json.dumps({
            "canonical_profile": profile,
            "identity": {"display_name": identity.display_name, "tone": identity.tone},
            "job": {"title": job.title, "company": job.company_name, "description": (job.raw_description or "")[:2000]},
            "resume_excerpt": resume_excerpt[:1500],
        })

        class LLMLetter(BaseModel):
            content_text: str

        llm = self._llm or LLMClient()
        result = await llm.complete_json(system=system, user=user, response_model=LLMLetter, temperature=0.3)
        check = self._truth.validate_document(result.content_text, profile, document_type="cover_letter")
        if not check.valid:
            raise ValueError(f"Cover letter truth check failed: {check.violations}")
        return result.content_text
