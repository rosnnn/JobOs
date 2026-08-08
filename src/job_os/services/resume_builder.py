"""Deterministic + optional LLM resume tailoring from canonical profile."""

from pathlib import Path
from typing import Any

from job_os.core.llm import LLMClient
from job_os.core.truth import TruthValidator
from job_os.models.identity import ProfessionalIdentity
from job_os.models.job import Job
from pydantic import BaseModel, Field


class TailoredResumeOutput(BaseModel):
    content_text: str
    keywords_injected: list[str] = Field(default_factory=list)
    method: str = "template"


class ResumeBuilder:
    def __init__(self) -> None:
        self._truth = TruthValidator()
        self._llm: LLMClient | None = None

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    async def tailor(
        self,
        *,
        profile: dict[str, Any],
        identity: ProfessionalIdentity,
        job: Job,
        use_llm: bool = False,
    ) -> TailoredResumeOutput:
        base = self._load_base_template(identity)
        keywords = self._select_keywords(identity, job)
        content = self._apply_template(base, profile, identity, job, keywords)

        if use_llm and self._has_llm_key():
            try:
                content = await self._tailor_with_llm(profile, identity, job, content)
                method = "llm"
            except Exception:
                method = "template"
        else:
            method = "template"

        check = self._truth.validate_document(content, profile, document_type="resume")
        if not check.valid:
            content = self._apply_template(base, profile, identity, job, keywords)
            method = "template_fallback"

        return TailoredResumeOutput(
            content_text=content,
            keywords_injected=keywords,
            method=method,
        )

    def _has_llm_key(self) -> bool:
        from job_os.config import get_settings

        s = get_settings()
        return bool(s.openai_api_key or s.anthropic_api_key or s.gemini_api_key)

    def _load_base_template(self, identity: ProfessionalIdentity) -> str:
        from job_os.config import get_settings

        settings = get_settings()
        for candidate in (
            Path(identity.base_resume_path) if identity.base_resume_path else None,
            Path("data/resumes") / f"{identity.slug}.md",
            settings.master_resume_path,
            Path("data/resumes/canonical_base.md"),
        ):
            if candidate and Path(candidate).exists():
                return Path(candidate).read_text(encoding="utf-8")
        return _default_template()

    def _select_keywords(self, identity: ProfessionalIdentity, job: Job) -> list[str]:
        job_text = f"{job.title} {job.raw_description or ''}".lower()
        selected = []
        for kw in identity.ats_keywords or []:
            if kw.lower() in job_text or len(selected) < 6:
                selected.append(kw)
            if len(selected) >= 8:
                break
        return selected[:8]

    def _apply_template(
        self,
        base: str,
        profile: dict,
        identity: ProfessionalIdentity,
        job: Job,
        keywords: list[str],
    ) -> str:
        name = profile.get("full_name", "Candidate")
        email = profile.get("email", "")
        phone = profile.get("phone", "")
        location = profile.get("location", "")

        skills = list(profile.get("skills", []))
        for kw in keywords:
            if kw not in skills:
                skills.append(kw)

        projects = profile.get("projects", [])
        emphasis = set(identity.project_emphasis or [])
        sorted_projects = sorted(
            projects,
            key=lambda p: sum(1 for e in emphasis if e.lower() in p.get("description", "").lower()),
            reverse=True,
        )

        project_lines = []
        for p in sorted_projects[:4]:
            tech = ", ".join(p.get("technologies", []))
            project_lines.append(f"- **{p.get('name', 'Project')}**: {p.get('description', '')} ({tech})")

        edu = profile.get("education", {})
        edu_line = f"{edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('graduation_year', '')})"

        headline = profile.get("headline", "")
        years = int(profile.get("experience_years", 0))
        if headline and years >= 1:
            summary = (
                f"{headline}. Applying for {job.title} at {job.company_name or 'target company'}. "
                f"Core stack: {', '.join(skills[:8])}."
            )
        elif years < 1:
            summary = (
                f"Entry-level {identity.role_focus} targeting {job.title} at {job.company_name or 'target company'}. "
                f"Skilled in {', '.join(skills[:6])}."
            )
        else:
            summary = (
                f"{identity.role_focus} with {years}+ year(s) of hands-on experience. "
                f"Targeting {job.title} at {job.company_name or 'target company'}. "
                f"Skills: {', '.join(skills[:8])}."
            )

        auth = profile.get("work_authorization", {})
        auth_line = ""
        if auth.get("requires_sponsorship"):
            auth_line = "Work authorization: Requires visa sponsorship. Willing to relocate internationally."

        content = base
        replacements = {
            "{{FULL_NAME}}": name,
            "{{EMAIL}}": email,
            "{{PHONE}}": phone,
            "{{LOCATION}}": location,
            "{{SUMMARY}}": summary,
            "{{SKILLS}}": ", ".join(skills),
            "{{PROJECTS}}": "\n".join(project_lines) if project_lines else "- See portfolio",
            "{{EDUCATION}}": edu_line,
            "{{TARGET_ROLE}}": job.title,
            "{{TARGET_COMPANY}}": job.company_name or "the company",
            "{{IDENTITY}}": identity.display_name,
            "{{KEYWORDS}}": ", ".join(keywords),
            "{{AUTHORIZATION}}": auth_line,
        }
        for token, value in replacements.items():
            content = content.replace(token, value)

        if "{{" in content:
            content = _inline_resume(name, email, phone, location, summary, skills, project_lines, edu_line, auth_line)

        return content.strip()

    async def _tailor_with_llm(
        self,
        profile: dict,
        identity: ProfessionalIdentity,
        job: Job,
        base_content: str,
    ) -> str:
        import json

        system = (
            "You tailor resumes for job applications. CRITICAL RULES:\n"
            "1. Use ONLY facts from the provided canonical profile JSON.\n"
            "2. Never invent employers, degrees, years of experience, or work authorization.\n"
            "3. Never claim US citizenship or clearance unless explicitly in profile.\n"
            "4. Emphasize relevant projects and ATS keywords truthfully.\n"
            "Respond with JSON: {\"content_text\": \"...\"}"
        )
        user = json.dumps({
            "canonical_profile": profile,
            "identity": {
                "slug": identity.slug,
                "role_focus": identity.role_focus,
                "ats_keywords": identity.ats_keywords,
            },
            "job": {
                "title": job.title,
                "company": job.company_name,
                "description": (job.raw_description or "")[:3000],
            },
            "base_resume": base_content,
        })

        class LLMResume(BaseModel):
            content_text: str

        result = await self._get_llm().complete_json(
            system=system, user=user, response_model=LLMResume, temperature=0.2
        )
        check = self._truth.validate_document(result.content_text, profile)
        if not check.valid:
            raise ValueError(f"LLM resume failed truth check: {check.violations}")
        return result.content_text


def _default_template() -> str:
    return """# {{FULL_NAME}}
{{EMAIL}} | {{PHONE}} | {{LOCATION}}

## Summary
{{SUMMARY}}

## Skills
{{SKILLS}}

## Projects
{{PROJECTS}}

## Education
{{EDUCATION}}

## Work Authorization
{{AUTHORIZATION}}
"""


def _inline_resume(
    name: str,
    email: str,
    phone: str,
    location: str,
    summary: str,
    skills: list,
    project_lines: list,
    edu_line: str,
    auth_line: str,
) -> str:
    lines = [
        f"# {name}",
        f"{email} | {phone} | {location}",
        "",
        "## Summary",
        summary,
        "",
        "## Skills",
        ", ".join(skills),
        "",
        "## Projects",
        *(project_lines or ["- Portfolio projects available on request"]),
        "",
        "## Education",
        edu_line,
    ]
    if auth_line:
        lines.extend(["", "## Work Authorization", auth_line])
    return "\n".join(lines)
