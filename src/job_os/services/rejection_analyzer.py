"""Analyze rejection patterns and suggest profile/resume fixes."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.application import Application
from job_os.models.email_message import EmailMessage
from job_os.services.profile_service import ProfileService


class RejectionAnalyzer:
    THEME_PATTERNS: list[tuple[str, str]] = [
        ("experience", r"more experience|years of experience|not enough experience"),
        ("sponsorship", r"sponsorship|visa|work authorization|authorized to work"),
        ("location", r"location|relocate|on-?site|hybrid"),
        ("skills", r"skills|qualifications|requirements|technical"),
        ("competition", r"other candidates|strong pool|many applicants"),
        ("role_filled", r"position filled|role closed|no longer hiring"),
    ]

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze(self) -> dict[str, Any]:
        stmt = select(EmailMessage).where(EmailMessage.classified_outcome == "rejected")
        result = await self._session.execute(stmt)
        rejections = list(result.scalars().all())

        themes: Counter[str] = Counter()
        reasons: list[str] = []
        for msg in rejections:
            if msg.rejection_reason:
                reasons.append(msg.rejection_reason)
                theme = self._classify_theme(msg.rejection_reason)
                if theme:
                    themes[theme] += 1

        suggestions = self._build_suggestions(themes)
        profile_fixes = await self._profile_fixes(themes)

        return {
            "total_rejections": len(rejections),
            "themes": dict(themes),
            "recent_reasons": reasons[:10],
            "suggestions": suggestions,
            "profile_fixes": profile_fixes,
        }

    def _classify_theme(self, text: str) -> str | None:
        import re

        lower = text.lower()
        for theme, pattern in self.THEME_PATTERNS:
            if re.search(pattern, lower, re.I):
                return theme
        return "other"

    def _build_suggestions(self, themes: Counter[str]) -> list[str]:
        suggestions: list[str] = []
        if themes.get("experience", 0) >= 2:
            suggestions.append(
                "Many rejections cite experience — emphasize projects, internships, and measurable impact on resume."
            )
        if themes.get("sponsorship", 0) >= 2:
            suggestions.append(
                "Target remote-first and visa-sponsorship-friendly companies; filter for explicit sponsorship mentions."
            )
        if themes.get("skills", 0) >= 2:
            suggestions.append(
                "Skill gaps detected — tailor resume keywords to each job description and highlight matching stack."
            )
        if themes.get("location", 0) >= 2:
            suggestions.append("Prioritize fully remote roles to reduce location-based rejections.")
        if not suggestions:
            suggestions.append("Keep applying — rejection volume is normal. Review top-ranked jobs for better fit.")
        return suggestions

    async def _profile_fixes(self, themes: Counter[str]) -> dict[str, Any]:
        profile = ProfileService().load()
        fixes: dict[str, Any] = {"screening_answers": {}, "headline_tweak": None}

        if themes.get("sponsorship", 0) >= 1:
            fixes["screening_answers"]["requires_sponsorship"] = "Yes"
            fixes["screening_answers"]["authorized_to_work_us"] = "No — require sponsorship"

        if themes.get("experience", 0) >= 1:
            fixes["headline_tweak"] = (
                f"{profile.get('headline', 'Software Engineer')} | Recent Graduate | Internship Experience"
            )
            fixes["emphasis"] = "Lead with internship projects and quantified outcomes in bullet points."

        return fixes

    async def apply_fixes_to_applications(self) -> int:
        """Mark rejected apps with fix suggestions in metadata."""
        analysis = await self.analyze()
        stmt = select(Application).where(Application.outcome == "rejected")
        result = await self._session.execute(stmt)
        count = 0
        for app in result.scalars().all():
            meta = app.metadata_ or {}
            meta["rejection_analysis"] = {
                "suggestions": analysis["suggestions"],
                "profile_fixes": analysis["profile_fixes"],
            }
            app.metadata_ = meta
            count += 1
        await self._session.flush()
        return count
