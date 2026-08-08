"""Detect whether a job URL can be auto-applied via browser."""

from __future__ import annotations

import re

from job_os.services.job_url_quality import (
    APPLYABLE_HINTS,
    LISTING_PATTERNS,
    is_real_job_posting,
)


def assess_apply_url(url: str, source: str = "", *, title: str = "") -> tuple[bool, str]:
    """Return (can_auto_apply, user_message)."""
    real, reason = is_real_job_posting(url, source=source, title=title)
    if not real:
        messages = {
            "listing_index_page": (
                "This is a job board listing page, not a real role. "
                "Use Discover jobs again — only direct posting links are kept."
            ),
            "remoteok_not_a_job_slug": (
                "RemoteOK link is not a real job posting. Pick roles with a company Apply URL."
            ),
            "himalayas_missing_apply_link": "Missing Himalayas application link for this role.",
            "not_verified_job_posting": (
                "URL is not a verified job posting (board index or scraped nav link). "
                "Only real ATS / apply links are supported."
            ),
        }
        return False, messages.get(reason, f"Not a real job posting ({reason}).")

    if not url or not url.startswith("http"):
        return False, "Missing job URL — open the posting from Jobs and try again."

    u = url.strip()
    for pat in LISTING_PATTERNS:
        if pat.search(u):
            return (
                False,
                "This link is a job board listing page, not an application form. "
                "Use jobs from Himalayas, Greenhouse, or Lever (direct Apply links), "
                "or click View job posting → Apply on the company site manually.",
            )

    if source == "remoteok" and "remote-jobs/remote-" not in u.lower():
        return (
            False,
            "RemoteOK listing URL cannot be auto-filled. Re-run Discover jobs or pick a role with a company Apply link.",
        )

    if any(h in u.lower() for h in APPLYABLE_HINTS):
        return True, "ATS apply page detected."

    # Job board detail pages may still have an Apply button — try browser
    if any(d in u.lower() for d in ("jobicy.com/jobs/", "himalayas.app/companies/", "remotive.com/remote-jobs/")):
        return True, "Job detail page — will try to open Apply link."

    if "apply" in u.lower() or "/jobs/" in u.lower():
        return True, "Possible apply page."

    return True, "Will attempt browser apply."
