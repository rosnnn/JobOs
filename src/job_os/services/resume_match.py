"""Match jobs to profile + resume/cover letter text (keyword overlap)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from job_os.config import get_settings
from job_os.services.profile_service import ProfileService


def _load_resume_text() -> str:
    settings = get_settings()
    parts: list[str] = []
    if settings.master_resume_path.exists():
        parts.append(settings.master_resume_path.read_text(encoding="utf-8", errors="replace"))
    resume_dir = settings.source_resume_dir
    if resume_dir.exists():
        for path in sorted(resume_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]:
            parts.append(path.name)
        for path in sorted(resume_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:2]:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    cover_dir = settings.cover_letter_upload_path
    if cover_dir.exists():
        for path in sorted(cover_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:2]:
            if path.suffix.lower() in (".md", ".txt"):
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def build_profile_corpus(profile: dict[str, Any] | None = None) -> tuple[list[str], str]:
    profile = profile or ProfileService().load()
    tokens: set[str] = set()
    for skill in profile.get("skills") or []:
        tokens.add(skill.lower().strip())
    for proj in profile.get("projects") or []:
        for tech in proj.get("technologies") or []:
            tokens.add(str(tech).lower().strip())
        tokens.add(str(proj.get("name", "")).lower())
    for emp in profile.get("employment") or []:
        tokens.add(str(emp.get("title", "")).lower())
    js = profile.get("job_search") or {}
    for kw in js.get("keywords") or []:
        tokens.add(str(kw).lower().strip())
    if profile.get("cover_letter_excerpt"):
        for word in re.findall(r"[a-z][a-z0-9+#.]{2,}", profile["cover_letter_excerpt"].lower()):
            if len(word) > 2:
                tokens.add(word)
    headline = profile.get("headline") or ""
    summary = profile.get("summary") or ""
    corpus = f"{headline} {summary} {_load_resume_text()}".lower()
    for word in re.findall(r"[a-z][a-z0-9+#.]{2,}", corpus):
        if len(word) > 2:
            tokens.add(word)
    return sorted(tokens), corpus


def score_job_match(
    *,
    title: str,
    description: str | None,
    company_name: str | None,
    profile: dict[str, Any] | None = None,
) -> float:
    """0.0–1.0 overlap between job title + skills (not whole resume word soup)."""
    profile = profile or ProfileService().load()
    skills = [s.lower().strip() for s in (profile.get("skills") or []) if len(s) > 2]
    tech_from_projects: list[str] = []
    for proj in profile.get("projects") or []:
        for tech in proj.get("technologies") or []:
            tech_from_projects.append(str(tech).lower().strip())
    tokens = list(dict.fromkeys(skills + tech_from_projects))
    if not tokens:
        return 0.0

    title_l = title.lower()
    desc_l = (description or "")[:8000].lower()
    hits = 0
    title_hits = 0
    for t in tokens:
        if len(t) < 3:
            continue
        if t in title_l:
            title_hits += 2
            hits += 2
        elif t in desc_l:
            hits += 1

    if hits == 0:
        return 0.0
    denom = max(len(tokens) * 1.2, 6)
    return round(min(1.0, (hits + title_hits * 0.5) / denom), 3)
