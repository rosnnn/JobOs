"""Scrape apply/listing pages for country locks missing from board APIs."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from job_os.services.location_eligibility import (
    GLOBAL_REMOTE_SOURCES,
    extract_location_locks_from_text,
    merge_apply_page_restrictions,
)
from job_os.schemas.jobs import JobIngest

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html[:120_000], "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)[:25_000]


async def enrich_ingest_location_from_apply_page(
    client: httpx.AsyncClient,
    ingest: JobIngest,
    *,
    profile_requires_sponsorship: bool = True,
) -> JobIngest:
    """
    Fetch apply URL when board API omitted country lock (Germany only, Brazil only, etc.).
    """
    if ingest.source not in GLOBAL_REMOTE_SOURCES:
        return ingest
    meta = dict(ingest.metadata or {})
    existing = meta.get("location_restrictions") or []
    if existing:
        return ingest
    if meta.get("location_enriched_from_apply_page"):
        return ingest
    url = (ingest.url or "").strip()
    if not url or not url.startswith("http"):
        return ingest
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            timeout=15.0,
        )
        if resp.status_code >= 400:
            return ingest
        text = _html_to_text(resp.text)
        # Some ATS embed restrictions in JSON-LD or data attributes
        text += " " + " ".join(re.findall(r'"location[^"]*"\s*:\s*"([^"]{2,80})"', resp.text[:80_000], re.I))
        if not extract_location_locks_from_text(text):
            return ingest
        loc, meta = merge_apply_page_restrictions(
            location=ingest.location,
            metadata=meta,
            apply_page_text=text,
        )
        ingest.location = loc
        ingest.metadata = meta
    except Exception:
        return ingest
    return ingest
