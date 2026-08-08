"""Shared UI filter logic for /jobs and profile catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from job_os.services.location_eligibility import offers_visa_sponsorship
from job_os.services.profile_job_search import _location_parts


@dataclass
class JobListFilters:
    status: str | None = None
    source: str | None = None
    is_remote: bool | None = None
    offers_sponsorship: bool | None = None
    fresher_friendly: bool | None = None
    internship: bool | None = None
    keyword: str | None = None


def location_tier(job: Any, profile: dict[str, Any]) -> int:
    """0 = user's city, 1 = user's country, 2 = remote/global, 3 = other."""
    city, country = _location_parts(profile)
    loc = (getattr(job, "location", None) or "").lower()
    title = (getattr(job, "title", None) or "").lower()
    desc = (getattr(job, "raw_description", None) or "").lower()
    text = f"{loc} {title} {desc}"

    if city and re.search(rf"\b{re.escape(city.lower())}\b", text):
        return 0
    if country and len(country) > 2 and re.search(rf"\b{re.escape(country.lower())}\b", text):
        return 1
    if getattr(job, "is_remote", False) or "remote" in text or "worldwide" in text:
        return 2
    return 3


def _job_text(job: Any) -> str:
    title = getattr(job, "title", "") or ""
    desc = getattr(job, "raw_description", "") or ""
    loc = getattr(job, "location", "") or ""
    return f"{title} {desc} {loc}".lower()


def _is_internship_job(job: Any) -> bool:
    meta = getattr(job, "parsed_metadata", None) or {}
    if meta.get("is_internship"):
        return True
    text = _job_text(job)
    return bool(re.search(r"\bintern(ship)?\b|\bapprentice\b|\btrainee\b|\bco-?op\b", text, re.I))


def _is_remote_job(job: Any) -> bool:
    if getattr(job, "is_remote", False):
        return True
    return "remote" in _job_text(job)


def _is_fresher_job(job: Any) -> bool:
    flag = getattr(job, "fresher_friendly", None)
    if flag is True:
        return True
    if flag is False:
        return False
    text = _job_text(job)
    if any(s in text for s in ("10+ years", "5+ years", "principal", "staff engineer", "director")):
        return False
    return bool(
        re.search(
            r"\bintern(ship)?\b|\bapprentice\b|\bentry[\s-]?level\b|\bjunior\b|\bgraduate\b|\bfresher\b|\b0[\s-]?2 years\b",
            text,
            re.I,
        )
    )


def _has_sponsorship(job: Any) -> bool:
    if getattr(job, "offers_sponsorship", None) is True:
        return True
    meta = getattr(job, "parsed_metadata", None) or {}
    if isinstance(meta, dict) and meta.get("visa_sponsorship") is True:
        return True
    return offers_visa_sponsorship(_job_text(job), job)


def _explicitly_no_sponsorship(job: Any) -> bool:
    text = _job_text(job)
    if any(
        phrase in text
        for phrase in (
            "no sponsorship",
            "unable to sponsor",
            "cannot sponsor",
            "will not sponsor",
            "no visa",
            "without sponsorship",
        )
    ):
        return True
    if getattr(job, "offers_sponsorship", None) is False:
        meta = getattr(job, "parsed_metadata", None) or {}
        return meta.get("visa_sponsorship") is False
    return False


def matches_ui_filters(job: Any, filters: JobListFilters | None) -> bool:
    if not filters:
        return True

    if filters.status and getattr(job, "status", None) != filters.status:
        return False

    if filters.source and getattr(job, "source", None) != filters.source:
        return False

    if filters.is_remote and not _is_remote_job(job):
        return False

    if filters.internship and not _is_internship_job(job):
        return False

    if filters.offers_sponsorship:
        if _explicitly_no_sponsorship(job):
            return False

    if filters.fresher_friendly:
        if getattr(job, "fresher_friendly", None) is False:
            return False
        if not _is_fresher_job(job):
            return False

    if filters.keyword:
        kw = filters.keyword.strip().lower()
        if not kw:
            return True
        parts = [p.strip() for p in re.split(r"[,;]+", kw) if p.strip()]
        text = _job_text(job)
        company = (getattr(job, "company_name", "") or "").lower()
        blob = f"{text} {company}"
        if not any(part in blob for part in parts):
            return False

    return True
