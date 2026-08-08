"""User job search preferences — Naukri/Glassdoor-style filters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_os.config import get_settings
from job_os.services.job_role_filter import is_software_engineering_role
from job_os.services.location_eligibility import is_location_eligible
from job_os.services.profile_job_search import merge_prefs_with_profile
from job_os.services.profile_service import ProfileService

DEFAULT_PREFERENCES: dict[str, Any] = {
    "remote_only": False,
    "internship": True,
    "full_time": True,
    "sponsorship": True,
    "fresher_friendly": True,
    "recent_days": 14,
    "keywords": ["software", "backend", "developer", "engineer", "intern", "graduate", "entry"],
    "exclude_keywords": [
        "senior",
        "principal",
        "staff",
        "director",
        "10+ years",
        "5+ years",
        "game tester",
        "survey taker",
        "copywriter",
        "bookkeeper",
        "merchandising",
        "fire fighter",
        "voice actor",
        "wellness coach",
        "marketing coordinator",
        "key account",
        "estimator",
        "elektriker",
        "servicetechniker",
    ],
    "require_title_software_match": True,
    "min_resume_match": 0.08,
    "experience_level": "recent_graduate_intern",
    "locations": ["global", "remote"],
    "auto_apply_enabled": True,
    "auto_apply_max_per_run": 10,
    "email_monitor_enabled": True,
    "software_only": True,
}

SOFTWARE_TITLE_HINTS = (
    "software",
    "developer",
    "engineer",
    "engineering",
    "programmer",
    "devops",
    "sre",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "data engineer",
    "machine learning",
    "ml ",
    "intern",
    "graduate engineer",
    "coding",
    "python",
    "java ",
    "javascript",
    "react",
    "node",
    "cloud engineer",
)


class PreferencesService:
    def __init__(self, path: Path | None = None):
        settings = get_settings()
        self._path = path or settings.job_preferences_path

    def load(self) -> dict[str, Any]:
        base = dict(DEFAULT_PREFERENCES)
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            base = {**base, **data}
        return merge_prefs_with_profile(base)

    def save(self, prefs: dict[str, Any]) -> dict[str, Any]:
        merged = {**DEFAULT_PREFERENCES, **prefs}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return merged

    def matches_job(self, job: Any, prefs: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
        """Return (matches, reject_reasons) for a Job ORM or dict-like object."""
        prefs = prefs or self.load()
        reasons: list[str] = []

        title = getattr(job, "title", "") or ""
        desc = getattr(job, "raw_description", "") or ""
        meta = getattr(job, "parsed_metadata", None) or {}
        text = f"{title} {desc} {getattr(job, 'location', '') or ''}".lower()

        if prefs.get("remote_only") and not getattr(job, "is_remote", False):
            if "remote" not in text:
                reasons.append("not_remote")

        if prefs.get("internship") and not prefs.get("full_time"):
            if not self._is_internship(text, meta):
                reasons.append("not_internship")

        if prefs.get("sponsorship"):
            # Prefer sponsorship — only hard-reject explicit "no sponsor" wording, not unknown
            if any(
                phrase in text
                for phrase in (
                    "no sponsorship",
                    "unable to sponsor",
                    "cannot sponsor",
                    "will not sponsor",
                    "no visa",
                    "must be authorized to work",
                    "without sponsorship",
                )
            ):
                reasons.append("no_sponsorship")
            elif getattr(job, "offers_sponsorship", None) is False and meta.get("visa_sponsorship") is False:
                pass  # unknown — still show job

        if prefs.get("fresher_friendly"):
            exp_level = prefs.get("experience_level", "")
            if exp_level == "recent_graduate_intern":
                senior_hits = ["10+ years", "5+ years", "principal", "staff engineer", "director"]
                if any(s in text for s in senior_hits):
                    reasons.append("too_senior")

        for kw in prefs.get("exclude_keywords", []):
            if kw.lower() in text:
                reasons.append(f"excluded:{kw}")

        keywords = prefs.get("keywords", [])
        if keywords and prefs.get("require_keyword_match", False):
            if not any(kw.lower() in text for kw in keywords):
                reasons.append("keyword_mismatch")

        if prefs.get("software_only", True):
            if prefs.get("require_title_software_match", True):
                ok_role, role_reason = is_software_engineering_role(title, desc)
                if not ok_role:
                    reasons.append(role_reason or "not_software_role")
            else:
                title_l = title.lower()
                if not any(hint in title_l for hint in SOFTWARE_TITLE_HINTS):
                    if not any(hint in text for hint in SOFTWARE_TITLE_HINTS):
                        reasons.append("not_software_role")

        profile = ProfileService().load()
        loc_ok, loc_reason = is_location_eligible(job, profile, prefs)
        if not loc_ok:
            reasons.append(loc_reason or "location_not_eligible")

        recent_days = prefs.get("recent_days")
        if recent_days and getattr(job, "discovered_at", None):
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(timezone.utc) - timedelta(days=int(recent_days))
            discovered = job.discovered_at
            if discovered.tzinfo is None:
                discovered = discovered.replace(tzinfo=timezone.utc)
            if discovered < cutoff:
                reasons.append("too_old")

        return len(reasons) == 0, reasons

    @staticmethod
    def _is_internship(text: str, meta: dict) -> bool:
        if meta.get("is_internship"):
            return True
        return bool(
            __import__("re").search(
                r"\bintern(ship)?\b|\bapprentice\b|\btrainee\b|\bco-?op\b", text, __import__("re").I
            )
        )
