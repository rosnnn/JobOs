"""Per-board job fetch implementations (APIs, RSS, ATS)."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from job_os.config import get_settings
from job_os.schemas.jobs import JobIngest
from job_os.services.job_role_filter import is_software_engineering_role, normalize_job_title
from job_os.services.job_source_registry import GREENHOUSE_BOARDS, LEVER_COMPANIES
from job_os.services.job_url_quality import is_real_job_posting
from job_os.services.location_eligibility import infer_offers_sponsorship, is_location_eligible
from job_os.services.profile_service import ProfileService

UA = {"User-Agent": "JobOS/0.1"}


def _probe(title: str, desc: str, loc: str, source: str, meta: dict, sponsor: bool | None = None) -> Any:
    return type(
        "Probe",
        (),
        {
            "title": title,
            "raw_description": desc,
            "location": loc,
            "is_remote": meta.get("is_remote", False),
            "source": source,
            "parsed_metadata": meta,
            "offers_sponsorship": sponsor,
        },
    )()


def _eligible(profile: dict, **kwargs) -> bool:
    return is_location_eligible(_probe(**kwargs), profile)[0]


def _ingest_from_fields(
    *,
    external_id: str,
    source: str,
    title: str,
    url: str,
    company: str | None,
    location: str,
    description: str,
    meta: dict,
    profile: dict,
) -> JobIngest | None:
    title = normalize_job_title(title)
    if not title:
        return None
    role_ok, _ = is_software_engineering_role(title, description)
    if not role_ok:
        return None
    ok, _ = is_real_job_posting(url, source=source, title=title)
    if not ok:
        return None
    text = f"{title} {description} {location}".lower()
    sponsor = infer_offers_sponsorship(text, meta)
    if sponsor is True:
        meta["visa_sponsorship"] = True
    elif sponsor is False:
        meta["visa_sponsorship"] = False
    if not _eligible(
        profile,
        title=title,
        desc=description,
        loc=location,
        source=source,
        meta=meta,
        sponsor=sponsor,
    ):
        return None
    return JobIngest(
        external_id=external_id[:256],
        source=source,
        title=title,
        url=url,
        company_name=company,
        location=location,
        raw_description=description,
        metadata=meta,
    )


async def discover_jsearch(client: httpx.AsyncClient, seeds: list[dict]) -> list[JobIngest]:
    """Google for Jobs — LinkedIn, Indeed, Glassdoor, Naukri, ZipRecruiter, etc."""
    settings = get_settings()
    api_key = settings.rapidapi_key
    if not api_key:
        return []

    profile = ProfileService().load()
    queries = [s.get("q") for s in seeds if s.get("q")] or ["software engineer intern"]
    jobs: list[JobIngest] = []
    seen: set[str] = set()

    for q in queries[:12]:
        try:
            resp = await client.get(
                "https://jsearch.p.rapidapi.com/search",
                params={
                    "query": q,
                    "page": "1",
                    "num_pages": str(min(settings.jsearch_pages_per_query, 5)),
                    "date_posted": "month",
                },
                headers={
                    "x-rapidapi-key": api_key,
                    "x-rapidapi-host": "jsearch.p.rapidapi.com",
                },
                timeout=90.0,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json().get("data", []):
                if not isinstance(item, dict):
                    continue
                title = item.get("job_title") or ""
                url = (item.get("job_apply_link") or "").strip()
                ext = str(item.get("job_id") or hashlib.sha256(url.encode()).hexdigest()[:16])
                if ext in seen:
                    continue
                seen.add(ext)
                publisher = item.get("job_publisher") or "unknown"
                loc_parts = [
                    item.get("job_city") or "",
                    item.get("job_state") or "",
                    item.get("job_country") or "",
                ]
                location = ", ".join(p for p in loc_parts if p).strip()
                desc = item.get("job_description") or ""
                is_remote = bool(item.get("job_is_remote")) or "remote" in f"{title} {desc}".lower()
                meta = {
                    "is_remote": is_remote,
                    "job_publisher": publisher,
                    "board_family": "google_for_jobs",
                    "is_internship": bool(re.search(r"intern|apprentice|new grad", title, re.I)),
                    "job_posted_at_timestamp": item.get("job_posted_at_timestamp"),
                }
                row = _ingest_from_fields(
                    external_id=ext,
                    source="jsearch",
                    title=title,
                    url=url,
                    company=item.get("employer_name"),
                    location=location,
                    description=desc,
                    meta=meta,
                    profile=profile,
                )
                if row:
                    row.metadata["original_publisher"] = publisher
                    jobs.append(row)
        except Exception:
            continue
    return jobs


async def discover_rss_feed(
    client: httpx.AsyncClient,
    *,
    source: str,
    feed_url: str,
    default_remote: bool = True,
) -> list[JobIngest]:
    profile = ProfileService().load()
    jobs: list[JobIngest] = []
    try:
        resp = await client.get(feed_url, headers=UA, timeout=45.0)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items:
            title_el = item.find("title") or item.find("atom:title", ns)
            link_el = item.find("link") or item.find("atom:link", ns)
            desc_el = item.find("description") or item.find("summary") or item.find("atom:summary", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            url = ""
            if link_el is not None:
                url = link_el.get("href") or (link_el.text or "").strip()
            desc = (desc_el.text or "").strip() if desc_el is not None else ""
            if not title or not url:
                continue
            ext = hashlib.sha256(url.encode()).hexdigest()[:16]
            meta = {
                "is_remote": default_remote or "remote" in f"{title} {desc}".lower(),
                "feed_url": feed_url,
            }
            row = _ingest_from_fields(
                external_id=ext,
                source=source,
                title=title,
                url=url,
                company=None,
                location="Remote" if meta["is_remote"] else "",
                description=desc,
                meta=meta,
                profile=profile,
            )
            if row:
                jobs.append(row)
    except Exception:
        return []
    return jobs


async def discover_greenhouse_api(client: httpx.AsyncClient, seeds: list[dict]) -> list[JobIngest]:
    profile = ProfileService().load()
    boards = [s.get("board") for s in seeds if s.get("board")] or list(GREENHOUSE_BOARDS)
    jobs: list[JobIngest] = []
    for board in boards[:40]:
        try:
            resp = await client.get(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                params={"content": "true"},
                headers=UA,
                timeout=30.0,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json().get("jobs", []):
                title = item.get("title") or ""
                url = (item.get("absolute_url") or "").strip()
                loc_obj = item.get("location") or {}
                location = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj)
                desc = ""
                if item.get("content"):
                    desc = re.sub(r"<[^>]+>", " ", item["content"])
                ext = str(item.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16])
                meta = {
                    "is_remote": "remote" in f"{title} {location} {desc}".lower(),
                    "greenhouse_board": board,
                    "updated_at": item.get("updated_at"),
                }
                row = _ingest_from_fields(
                    external_id=ext,
                    source="greenhouse",
                    title=title,
                    url=url,
                    company=board.replace("-", " ").title(),
                    location=location or "",
                    description=desc,
                    meta=meta,
                    profile=profile,
                )
                if row:
                    jobs.append(row)
        except Exception:
            continue
    return jobs


async def discover_lever_api(client: httpx.AsyncClient, seeds: list[dict]) -> list[JobIngest]:
    profile = ProfileService().load()
    companies = [s.get("board") for s in seeds if s.get("board")] or list(LEVER_COMPANIES)
    jobs: list[JobIngest] = []
    for company in companies[:30]:
        try:
            resp = await client.get(
                f"https://api.lever.co/v0/postings/{company}",
                params={"mode": "json"},
                headers=UA,
                timeout=30.0,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json():
                title = item.get("text") or ""
                url = (item.get("hostedUrl") or item.get("applyUrl") or "").strip()
                location = (item.get("categories", {}) or {}).get("location") or ""
                desc = ""
                lists = item.get("lists") or []
                if lists:
                    desc = " ".join(
                        li.get("text", "") + " " + " ".join(str(x) for x in li.get("content", []))
                        for li in lists
                    )
                ext = str(item.get("id") or hashlib.sha256(url.encode()).hexdigest()[:16])
                meta = {
                    "is_remote": "remote" in f"{title} {location} {desc}".lower(),
                    "lever_company": company,
                    "created_at": item.get("createdAt"),
                }
                row = _ingest_from_fields(
                    external_id=ext,
                    source="lever",
                    title=title,
                    url=url,
                    company=company.replace("-", " ").title(),
                    location=location,
                    description=desc,
                    meta=meta,
                    profile=profile,
                )
                if row:
                    jobs.append(row)
        except Exception:
            continue
    return jobs


async def discover_findwork(client: httpx.AsyncClient, seeds: list[dict]) -> list[JobIngest]:
    settings = get_settings()
    token = settings.findwork_api_key
    if not token:
        return []

    profile = ProfileService().load()
    queries = [s.get("q") for s in seeds if s.get("q")] or ["python developer"]
    jobs: list[JobIngest] = []
    seen: set[str] = set()

    for q in queries[:8]:
        try:
            resp = await client.get(
                "https://findwork.dev/api/jobs/",
                params={"search": q, "location": "remote"},
                headers={"Authorization": f"Token {token}"},
                timeout=45.0,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json().get("results", []):
                url = (item.get("url") or "").strip()
                ext = hashlib.sha256(url.encode()).hexdigest()[:16]
                if ext in seen:
                    continue
                seen.add(ext)
                title = item.get("role") or ""
                desc = item.get("description") or ""
                meta = {"is_remote": True, "keywords": item.get("keywords") or [], "date": item.get("date")}
                row = _ingest_from_fields(
                    external_id=ext,
                    source="findwork",
                    title=title,
                    url=url,
                    company=item.get("company_name"),
                    location="Remote",
                    description=desc,
                    meta=meta,
                    profile=profile,
                )
                if row:
                    jobs.append(row)
        except Exception:
            continue
    return jobs
