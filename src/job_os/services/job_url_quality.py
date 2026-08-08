"""Only ingest, list, and apply to real per-role job postings — not board indexes or scraped nav links."""

from __future__ import annotations

import re
from urllib.parse import urlparse

LISTING_PATTERNS = [
    re.compile(r"remoteok\.com/remote-jobs/?$", re.I),
    re.compile(r"remoteok\.com/?$", re.I),
    re.compile(r"remotive\.com/remote-jobs/?$", re.I),
    re.compile(r"jobicy\.com/?$", re.I),
    re.compile(r"wellfound\.com/jobs/?$", re.I),
    re.compile(r"ycombinator\.com/jobs/?$", re.I),
]

APPLYABLE_HINTS = [
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "ashbyhq.com",
    "applytojob.com",
    "breezy.hr",
    "smartrecruiters.com",
    "icims.com",
    "jobs.lever.co",
    "boards.greenhouse.io",
]

# Nav / index link titles from HTML scraping (not real roles)
JUNK_TITLES = frozenset(
    {
        "jobs",
        "careers",
        "apply",
        "open roles",
        "open positions",
        "view all",
        "see all jobs",
        "job openings",
        "work with us",
        "join us",
        "current openings",
    }
)

GREENHOUSE_JOB = re.compile(
    r"boards\.greenhouse\.io/[^/]+/jobs/\d+",
    re.I,
)
LEVER_JOB = re.compile(
    r"jobs\.lever\.co/[^/]+/[a-f0-9-]{10,}",
    re.I,
)
REMOTEOK_JOB = re.compile(r"remoteok\.com/remote-jobs/remote-", re.I)
REMOTIVE_JOB = re.compile(r"remotive\.com/remote-jobs/[a-z0-9-]+", re.I)
JOBICY_JOB = re.compile(r"jobicy\.com/jobs/\d+", re.I)
HIMALAYAS_JOB = re.compile(r"himalayas\.app/(jobs|companies)/", re.I)


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def is_listing_index_url(url: str) -> bool:
    if not url:
        return True
    u = url.strip()
    for pat in LISTING_PATTERNS:
        if pat.search(u):
            return True
    low = u.lower().rstrip("/")
    if low.endswith("/remote-jobs") or low.endswith("/jobs"):
        if not REMOTIVE_JOB.search(u) and not REMOTEOK_JOB.search(u) and not JOBICY_JOB.search(u):
            return True
    return False


def is_real_job_posting(
    url: str,
    *,
    source: str = "",
    title: str = "",
) -> tuple[bool, str]:
    """
    Return (is_real, reject_reason).
    Used at discovery ingest, job catalog, application prep, and DB cleanup.
    """
    if not url or not url.startswith("http"):
        return False, "missing_or_invalid_url"

    u = url.strip()
    if len(u) < 12:
        return False, "url_too_short"

    host = _host(u)
    if not host or host in ("localhost", "example.com", "example.org"):
        return False, "invalid_host"

    if is_listing_index_url(u):
        return False, "listing_index_page"

    t = (title or "").strip().lower()
    if len(t) < 5:
        return False, "title_too_short"
    if t in JUNK_TITLES or len(t) > 200:
        return False, "junk_title"

    src = (source or "").lower()

    if src == "himalayas":
        if any(h in u.lower() for h in APPLYABLE_HINTS):
            return True, ""
        if HIMALAYAS_JOB.search(u) or (host and "himalayas.app" in host):
            return True, ""
        if host and host not in ("himalayas.app", "www.himalayas.app"):
            return True, ""
        return False, "himalayas_missing_apply_link"

    if src == "remoteok":
        if REMOTEOK_JOB.search(u):
            return True, ""
        if "remoteok.com" not in u.lower():
            return True, ""
        return False, "remoteok_not_a_job_slug"

    if src == "remotive":
        if REMOTIVE_JOB.search(u):
            return True, ""
        return False, "remotive_not_job_detail"

    if src == "jobicy":
        if JOBICY_JOB.search(u) or any(h in u.lower() for h in APPLYABLE_HINTS):
            return True, ""
        return False, "jobicy_not_job_detail"

    if src in ("greenhouse",):
        if GREENHOUSE_JOB.search(u):
            return True, ""
        return False, "greenhouse_not_job_url"

    if src in ("lever",):
        if LEVER_JOB.search(u):
            return True, ""
        return False, "lever_not_job_url"

    if src.startswith("adzuna_"):
        if "adzuna" in u.lower() and "redirect" not in u.lower():
            # Adzuna redirect URLs are real aggregator → employer links
            if "/land/" in u or "redirect" in u:
                return True, ""
        if host and "adzuna" not in host:
            return True, ""
        return False, "adzuna_invalid_redirect"

    if any(h in u.lower() for h in APPLYABLE_HINTS):
        return True, ""

    if GREENHOUSE_JOB.search(u) or LEVER_JOB.search(u):
        return True, ""

    if REMOTIVE_JOB.search(u) or JOBICY_JOB.search(u) or HIMALAYAS_JOB.search(u):
        return True, ""

    if src == "arbeitnow" and "/jobs/" in u.lower():
        return True, ""

    # Generic scraped links: reject unless clearly a job path
    if src in ("yc_jobs", "wellfound", "generic"):
        return False, "generic_board_scrape"

    if re.search(r"/(jobs?|careers?|positions?|openings?)/[^/]+", u, re.I):
        return True, ""

    if "apply" in u.lower() and host and "linkedin.com/feed" not in u.lower():
        return True, ""

    return False, "not_verified_job_posting"


def is_real_job_record(job: object) -> tuple[bool, str]:
    url = getattr(job, "url", "") or ""
    source = getattr(job, "source", "") or ""
    title = getattr(job, "title", "") or ""
    return is_real_job_posting(url, source=source, title=title)
