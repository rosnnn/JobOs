import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.config import get_settings
from job_os.models.job import Job
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.schemas.jobs import JobIngest
from job_os.services.job_posted_at import parse_posted_at
from job_os.services.job_role_filter import is_software_engineering_role, normalize_job_title
from job_os.services.job_url_quality import is_real_job_posting
from job_os.services.apply_page_location import enrich_ingest_location_from_apply_page
from job_os.services.board_fetchers import (
    discover_findwork,
    discover_greenhouse_api,
    discover_jsearch,
    discover_lever_api,
    discover_rss_feed,
)
from job_os.services.browser_board_scrapers import (
    board_scrape_snapshot,
    discover_linkedin_browser,
    discover_wellfound_browser,
)
from job_os.services.credentials_service import CredentialsService
from job_os.services.job_source_registry import priority_index
from job_os.services.location_eligibility import infer_offers_sponsorship, is_location_eligible
from job_os.services.profile_service import ProfileService


class JobDiscoveryAgent(BaseAgent):
    """Discovers jobs from configured sources. Phase 1: HTTP + heuristic parsing."""

    name = "job_discovery"
    version = "0.1.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        settings = get_settings()
        sources = ctx.scratchpad.get("discovery_sources", [])
        profile = ProfileService().load()
        from job_os.services.profile_job_search import _adzuna_country_code, build_job_search_block

        js = profile.get("job_search") or build_job_search_block(profile)
        home = js.get("home_country") or ""
        primary_adzuna = f"adzuna_{_adzuna_country_code(home)}"

        sources = sorted(
            sources,
            key=lambda s: priority_index(s["source"], primary_adzuna),
        )
        discovered: list[JobIngest] = []
        errors: list[str] = []
        source_counts: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:

            async def _fetch_one(source_cfg: dict) -> tuple[str, list[JobIngest] | Exception]:
                source = source_cfg["source"]
                seeds = source_cfg.get("seeds") or []
                try:
                    jobs = await self._discover_source(client, source, seeds, settings)
                    return source, jobs
                except Exception as exc:
                    return source, exc

            results = await asyncio.gather(*[_fetch_one(cfg) for cfg in sources])

        for source, outcome in results:
            if isinstance(outcome, Exception):
                errors.append(f"{source}:{outcome}")
                source_counts[source] = 0
                await self._emit(
                    ctx, msg, "job_discovery.source_error",
                    {"source": source, "error": str(outcome)}, severity="warning",
                )
            else:
                discovered.extend(outcome)
                source_counts[source] = len(outcome)

        if not settings.adzuna_app_id and any(s.startswith("adzuna_") for s in source_counts):
            errors.append("adzuna:missing_keys — set ADZUNA_APP_ID and ADZUNA_APP_KEY for Indeed/Naukri/Glassdoor")
        if not settings.rapidapi_key and "jsearch" in source_counts:
            errors.append("jsearch:missing_key — set RAPIDAPI_KEY for LinkedIn/Indeed/Glassdoor via JSearch")
        creds = CredentialsService().load()
        linkedin_email = creds.get("linkedin_email") or settings.linkedin_email
        linkedin_password = creds.get("linkedin_password") or settings.linkedin_password
        wellfound_email = creds.get("wellfound_email") or settings.wellfound_email
        wellfound_password = creds.get("wellfound_password") or settings.wellfound_password

        if "linkedin" in source_counts and (not linkedin_email or not linkedin_password):
            errors.append("linkedin:missing_credentials — set LINKEDIN_EMAIL and LINKEDIN_PASSWORD")
        if "wellfound" in source_counts and (not wellfound_email or not wellfound_password):
            errors.append("wellfound:missing_credentials — set WELLFOUND_EMAIL and WELLFOUND_PASSWORD")

        cap = settings.max_jobs_discovered_per_run
        to_persist = discovered if cap <= 0 else discovered[:cap]

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            persisted = await self._persist_jobs(to_persist, client)

        ctx.scratchpad["discovered_job_ids"] = [str(j.id) for j in persisted]
        ctx.scratchpad["source_counts"] = source_counts
        ctx.scratchpad["source_status"] = board_scrape_snapshot()

        await self._emit(
            ctx,
            msg,
            "job_discovery.completed",
            {"discovered": len(discovered), "persisted": len(persisted), "errors": errors, "by_source": source_counts},
        )

        return AgentResult(
            success=True,
            output={
                "job_count": len(persisted),
                "job_ids": [str(j.id) for j in persisted],
                "errors": errors,
                "by_source": source_counts,
                "by_source_status": board_scrape_snapshot(),
            },
            next_step_hint="eligibility",
        )

    async def _discover_source(
        self,
        client: httpx.AsyncClient,
        source: str,
        seeds: list[dict],
        settings: Any,
    ) -> list[JobIngest]:
        if source == "remoteok":
            return await self._discover_remoteok(client)
        if source == "remotive":
            return await self._discover_remotive(client)
        if source == "jobicy":
            return await self._discover_jobicy(client)
        if source == "arbeitnow":
            return await self._discover_arbeitnow(client)
        if source == "himalayas":
            return await self._discover_himalayas(client, seeds, settings)
        if source == "linkedin":
            return await discover_linkedin_browser(seeds)
        if source == "wellfound":
            return await discover_wellfound_browser(seeds)
        if source == "jsearch":
            return await discover_jsearch(client, seeds)
        if source == "findwork":
            return await discover_findwork(client, seeds)
        if source == "greenhouse":
            return await discover_greenhouse_api(client, seeds)
        if source == "lever":
            return await discover_lever_api(client, seeds)
        if source == "weworkremotely":
            return await discover_rss_feed(
                client,
                source="weworkremotely",
                feed_url="https://weworkremotely.com/categories/remote-programming-jobs.rss",
            )
        if source == "jobspresso":
            return await discover_rss_feed(
                client, source="jobspresso", feed_url="https://jobspresso.co/feed/"
            )
        if source.startswith("adzuna_"):
            country = source.replace("adzuna_", "")
            all_adzuna: list[JobIngest] = []
            seed_list = seeds or [{"what": "software engineer"}]
            for seed in seed_list:
                what = seed.get("what", "software engineer")
                batch = await self._discover_adzuna(client, country, what, settings)
                all_adzuna.extend(batch)
            return all_adzuna
        if source in ("yc_jobs", "startup_jobs"):
            return await self._discover_generic_listing(client, source, seeds)
        return []

    @staticmethod
    def _location_probe(
        *,
        title: str,
        desc: str,
        loc: str,
        source: str,
        meta: dict,
        sponsor: bool | None = None,
    ) -> Any:
        return type(
            "Probe",
            (),
            {
                "title": title,
                "raw_description": desc,
                "location": loc,
                "is_remote": meta.get("is_remote", True),
                "source": source,
                "parsed_metadata": meta,
                "offers_sponsorship": sponsor,
            },
        )()

    def _passes_location(self, profile: dict, **kwargs) -> bool:
        return is_location_eligible(self._location_probe(**kwargs), profile)[0]

    async def _discover_remoteok(self, client: httpx.AsyncClient) -> list[JobIngest]:
        profile = ProfileService().load()
        resp = await client.get("https://remoteok.com/api", headers={"User-Agent": "JobOS/0.1"})
        resp.raise_for_status()
        data = resp.json()
        jobs: list[JobIngest] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            url = (item.get("apply_url") or item.get("url") or "").strip()
            if not url or url.rstrip("/").lower().endswith("/remote-jobs"):
                continue
            title = item.get("position", item.get("title", "Unknown"))
            title = normalize_job_title(title)
            ok, _ = is_real_job_posting(url, source="remoteok", title=title)
            if not ok:
                continue
            role_ok, _ = is_software_engineering_role(title, item.get("description", ""))
            if not role_ok:
                continue
            loc = item.get("location") or ""
            desc = item.get("description", "")
            meta = {"is_remote": True, "location_restrictions": [loc] if loc else [], "tags": item.get("tags", []), "date": item.get("date")}
            probe = type("Probe", (), {"title": title, "raw_description": desc, "location": loc, "is_remote": True, "source": "remoteok", "parsed_metadata": meta, "offers_sponsorship": infer_offers_sponsorship(f"{title} {desc} {loc}", meta)})()
            if not is_location_eligible(probe, profile)[0]:
                continue
            jobs.append(
                JobIngest(
                    external_id=str(item["id"]),
                    source="remoteok",
                    title=title,
                    url=url,
                    company_name=item.get("company"),
                    location=loc,
                    raw_description=desc,
                    metadata=meta,
                )
            )
        return jobs

    async def _discover_remotive(self, client: httpx.AsyncClient) -> list[JobIngest]:
        profile = ProfileService().load()
        resp = await client.get(
            "https://remotive.com/api/remote-jobs?category=software-dev",
            headers={"User-Agent": "JobOS/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
        jobs: list[JobIngest] = []
        for item in data.get("jobs", []):
            title = normalize_job_title(item.get("title", ""))
            url = (item.get("url") or "").strip()
            ok, _ = is_real_job_posting(url, source="remotive", title=title)
            if not ok:
                continue
            role_ok, _ = is_software_engineering_role(title, item.get("description", ""))
            if not role_ok:
                continue
            req_loc = (item.get("candidate_required_location") or "").strip()
            desc = item.get("description", "")
            text = f"{title} {desc} {req_loc}".lower()
            meta = {
                "is_remote": True,
                "candidate_required_location": req_loc,
                "location_restrictions": [req_loc] if req_loc else [],
                "is_internship": bool(re.search(r"intern", title, re.I)),
                "tags": item.get("tags", []),
                "publication_date": item.get("publication_date"),
            }
            sponsor = infer_offers_sponsorship(text, meta)
            probe = type(
                "Probe",
                (),
                {
                    "title": title,
                    "raw_description": desc,
                    "location": req_loc,
                    "is_remote": True,
                    "source": "remotive",
                    "parsed_metadata": meta,
                    "offers_sponsorship": sponsor,
                },
            )()
            if not is_location_eligible(probe, profile)[0]:
                continue
            jobs.append(
                JobIngest(
                    external_id=str(item.get("id", hashlib.sha256(title.encode()).hexdigest()[:16])),
                    source="remotive",
                    title=title,
                    url=url,
                    company_name=item.get("company_name"),
                    location=req_loc,
                    raw_description=desc,
                    metadata={
                        **meta,
                        "visa_sponsorship": True if sponsor is True else False if sponsor is False else None,
                    },
                )
            )
        return jobs

    async def _discover_jobicy(self, client: httpx.AsyncClient) -> list[JobIngest]:
        profile = ProfileService().load()
        resp = await client.get(
            "https://jobicy.com/api/v2/remote-jobs?count=200&tag=dev",
            headers={"User-Agent": "JobOS/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
        jobs: list[JobIngest] = []
        for item in data.get("jobs", []):
            title = normalize_job_title(item.get("jobTitle", ""))
            url = (item.get("url") or "").strip()
            ok, _ = is_real_job_posting(url, source="jobicy", title=title)
            if not ok:
                continue
            role_ok, _ = is_software_engineering_role(title, item.get("jobDescription", ""))
            if not role_ok:
                continue
            loc = (item.get("jobGeo") or "").strip()
            desc = item.get("jobDescription", "")
            meta = {
                "is_remote": True,
                "location_restrictions": [loc] if loc else [],
                "is_internship": bool(re.search(r"intern", title, re.I)),
                "pub_date": item.get("pubDate"),
            }
            if not self._passes_location(
                profile,
                title=title,
                desc=desc,
                loc=loc,
                source="jobicy",
                meta=meta,
                sponsor=infer_offers_sponsorship(f"{title} {desc} {loc}", meta),
            ):
                continue
            jobs.append(
                JobIngest(
                    external_id=str(item.get("id", "")),
                    source="jobicy",
                    title=title,
                    url=url,
                    company_name=item.get("companyName"),
                    location=loc,
                    raw_description=desc,
                    metadata=meta,
                )
            )
        return jobs

    async def _discover_arbeitnow(self, client: httpx.AsyncClient) -> list[JobIngest]:
        profile = ProfileService().load()
        resp = await client.get(
            "https://www.arbeitnow.com/api/job-board-api",
            headers={"User-Agent": "JobOS/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()
        jobs: list[JobIngest] = []
        for item in data.get("data", []):
            title = normalize_job_title(item.get("title", ""))
            tags = item.get("tags", []) or []
            desc = item.get("description", "")
            url = (item.get("url") or "").strip()
            role_ok, _ = is_software_engineering_role(title, desc)
            if not role_ok:
                continue
            ok, _ = is_real_job_posting(url, source="arbeitnow", title=title)
            if not ok:
                continue
            text = f"{title} {desc}".lower()
            loc = (item.get("location") or "").strip()
            meta = {
                "is_remote": item.get("remote", False) or "remote" in text,
                "location_restrictions": [loc] if loc else [],
                "is_internship": bool(re.search(r"intern", text, re.I)),
                "tags": tags,
                "visa_sponsorship": item.get("visa_sponsorship"),
            }
            if not self._passes_location(
                profile,
                title=title,
                desc=desc,
                loc=loc,
                source="arbeitnow",
                meta=meta,
                sponsor=infer_offers_sponsorship(text, meta),
            ):
                continue
            jobs.append(
                JobIngest(
                    external_id=str(item.get("slug", hashlib.sha256(title.encode()).hexdigest()[:16])),
                    source="arbeitnow",
                    title=title,
                    url=url,
                    company_name=item.get("company_name"),
                    location=loc,
                    raw_description=desc,
                    metadata=meta,
                )
            )
        return jobs

    async def _discover_himalayas(
        self, client: httpx.AsyncClient, seeds: list[dict] | None = None, settings: Any = None
    ) -> list[JobIngest]:
        settings = settings or get_settings()
        queries = [s.get("q") for s in (seeds or []) if s.get("q")]
        if not queries:
            queries = [
                "software engineer remote",
                "backend developer intern",
                "graduate software engineer",
            ]
        queries = queries[: settings.himalayas_max_queries]
        max_pages = settings.himalayas_max_pages
        profile = ProfileService().load()
        jobs: list[JobIngest] = []
        seen: set[str] = set()
        for q in queries:
            page = 1
            while page <= max_pages:
                resp = await client.get(
                    "https://himalayas.app/jobs/api/search",
                    params={"q": q, "page": page},
                    headers={"User-Agent": "JobOS/0.1"},
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                batch = data.get("jobs", [])
                if not batch:
                    break
                for item in batch:
                    if not isinstance(item, dict):
                        continue
                    title = normalize_job_title(item.get("title") or "")
                    if not title:
                        continue
                    role_ok, _ = is_software_engineering_role(
                        title, item.get("description") or item.get("excerpt") or ""
                    )
                    if not role_ok:
                        continue
                    ext = str(item.get("guid") or hashlib.sha256(title.encode()).hexdigest()[:16])
                    if ext in seen:
                        continue
                    seen.add(ext)
                    desc = item.get("description") or item.get("excerpt") or ""
                    company = item.get("companyName")
                    raw_restrictions = item.get("locationRestrictions") or []
                    if isinstance(raw_restrictions, str):
                        raw_restrictions = [raw_restrictions]
                    loc = " ".join(str(x) for x in raw_restrictions)[:240]
                    text = f"{title} {desc} {loc}".lower()
                    apply_url = (item.get("applicationLink") or "").strip()
                    ok, _ = is_real_job_posting(apply_url, source="himalayas", title=title)
                    if not ok:
                        continue
                    meta = {
                        "location_restrictions": [str(x) for x in raw_restrictions if x],
                        "is_remote": True,
                        "board_family": "global_remote",
                        "is_internship": bool(re.search(r"intern", text, re.I)),
                        "pub_date": item.get("pubDate"),
                    }
                    sponsor = infer_offers_sponsorship(text, meta)
                    if sponsor is True:
                        meta["visa_sponsorship"] = True
                    elif sponsor is False:
                        meta["visa_sponsorship"] = False
                    probe = type(
                        "Probe",
                        (),
                        {
                            "title": title,
                            "raw_description": desc,
                            "location": loc,
                            "is_remote": True,
                            "source": "himalayas",
                            "parsed_metadata": meta,
                            "offers_sponsorship": sponsor,
                        },
                    )()
                    eligible, _ = is_location_eligible(probe, profile)
                    if not eligible:
                        continue
                    jobs.append(
                        JobIngest(
                            external_id=ext,
                            source="himalayas",
                            title=title,
                            url=apply_url,
                            company_name=company,
                            location=loc,
                            raw_description=desc,
                            metadata={
                                **meta,
                                "visa_sponsorship": meta.get("visa_sponsorship"),
                            },
                        )
                    )
                page += 1
        return jobs

    async def _discover_adzuna(
        self,
        client: httpx.AsyncClient,
        country: str,
        what: str,
        settings: Any = None,
    ) -> list[JobIngest]:
        settings = settings or get_settings()
        profile = ProfileService().load()
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            return []
        board = {
            "in": "indeed_naukri_aggregate",
            "us": "indeed_glassdoor_aggregate",
            "gb": "indeed_aggregate",
        }.get(country, "job_aggregate")
        jobs: list[JobIngest] = []
        page = 1
        max_pages = settings.adzuna_max_pages
        while page <= max_pages:
            resp = await client.get(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}",
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": what,
                    "results_per_page": 50,
                    "max_days_old": 30,
                },
                headers={"User-Agent": "JobOS/0.1"},
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                title = normalize_job_title(item.get("title", ""))
                desc = item.get("description", "")
                url = (item.get("redirect_url") or item.get("url") or "").strip()
                role_ok, _ = is_software_engineering_role(title, desc)
                if not role_ok:
                    continue
                ok, _ = is_real_job_posting(url, source=f"adzuna_{country}", title=title)
                if not ok:
                    continue
                text = f"{title} {desc}".lower()
                loc = (item.get("location", {}) or {}).get("display_name") or ""
                meta = {
                    "is_remote": "remote" in text,
                    "board_family": board,
                    "location_restrictions": [loc] if loc else [],
                    "is_internship": bool(re.search(r"intern", text, re.I)),
                    "created": item.get("created"),
                }
                sponsor = infer_offers_sponsorship(text, meta)
                if sponsor is True:
                    meta["visa_sponsorship"] = True
                elif sponsor is False:
                    meta["visa_sponsorship"] = False
                if not self._passes_location(
                    profile,
                    title=title,
                    desc=desc,
                    loc=loc,
                    source=f"adzuna_{country}",
                    meta=meta,
                    sponsor=sponsor,
                ):
                    continue
                jobs.append(
                    JobIngest(
                        external_id=str(item.get("id", "")),
                        source=f"adzuna_{country}",
                        title=title,
                        url=url,
                        company_name=item.get("company", {}).get("display_name"),
                        location=loc,
                        raw_description=desc,
                        metadata=meta,
                    )
                )
            page += 1
        return jobs

    async def _discover_from_seeds(
        self,
        client: httpx.AsyncClient,
        source: str,
        seeds: list[dict],
    ) -> list[JobIngest]:
        jobs: list[JobIngest] = []
        for seed in seeds:
            url = seed.get("url")
            if not url:
                continue
            resp = await client.get(url, headers={"User-Agent": "JobOS/0.1"})
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for link in soup.select("a[href*='jobs'], a[href*='job'], a.opening"):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if len(title) < 5 or len(title) > 200:
                    continue
                full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                ok, _ = is_real_job_posting(full_url, source=source, title=title)
                if not ok:
                    continue
                ext_id = hashlib.sha256(full_url.encode()).hexdigest()[:16]
                jobs.append(
                    JobIngest(
                        external_id=ext_id,
                        source=source,
                        title=title,
                        url=full_url,
                        company_name=seed.get("board"),
                        metadata={"seed_url": url},
                    )
                )
        return jobs

    async def _discover_generic_listing(
        self,
        client: httpx.AsyncClient,
        source: str,
        seeds: list[dict],
    ) -> list[JobIngest]:
        jobs: list[JobIngest] = []
        for seed in seeds:
            url = seed.get("url")
            if not url:
                continue
            resp = await client.get(url, headers={"User-Agent": "JobOS/0.1"})
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if not text or len(text) < 8:
                    continue
                if not any(k in href.lower() for k in ("job", "career", "position", "opening")):
                    continue
                full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                ext_id = hashlib.sha256(full_url.encode()).hexdigest()[:16]
                jobs.append(
                    JobIngest(
                        external_id=ext_id,
                        source=source,
                        title=text[:200],
                        url=full_url,
                        metadata={"seed_url": url},
                    )
                )
        return jobs

    async def _persist_jobs(
        self, jobs: list[JobIngest], client: httpx.AsyncClient | None = None
    ) -> list[Job]:
        if client is None:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as owned:
                return await self._persist_jobs(jobs, owned)

        persisted: list[Job] = []
        profile = ProfileService().load()
        requires_sponsor = bool(
            (profile.get("work_authorization") or {}).get("requires_sponsorship", True)
        )
        for ingest in jobs:
            ingest = await enrich_ingest_location_from_apply_page(
                client, ingest, profile_requires_sponsorship=requires_sponsor
            )
            ingest.title = normalize_job_title(ingest.title)
            ok, reason = is_real_job_posting(
                ingest.url, source=ingest.source, title=ingest.title
            )
            if not ok:
                continue
            role_ok, _ = is_software_engineering_role(ingest.title, ingest.raw_description)
            if not role_ok:
                continue
            meta = dict(ingest.metadata or {})
            text = f"{ingest.title} {ingest.raw_description or ''} {ingest.location or ''}"
            sponsor = infer_offers_sponsorship(text, meta)
            probe = self._location_probe(
                title=ingest.title,
                desc=ingest.raw_description or "",
                loc=ingest.location or "",
                source=ingest.source,
                meta=meta,
                sponsor=sponsor,
            )
            eligible, loc_reason = is_location_eligible(probe, profile)
            if not eligible:
                continue
            stmt = select(Job).where(
                Job.source == ingest.source,
                Job.external_id == ingest.external_id,
            )
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()
            posted = parse_posted_at(ingest.metadata)
            if existing:
                existing.location = ingest.location or existing.location
                existing.parsed_metadata = {**(existing.parsed_metadata or {}), **meta}
                existing.discovered_at = datetime.now(timezone.utc)
                re_probe = self._location_probe(
                    title=existing.title or ingest.title,
                    desc=existing.raw_description or ingest.raw_description or "",
                    loc=existing.location or "",
                    source=existing.source,
                    meta=existing.parsed_metadata or meta,
                    sponsor=sponsor,
                )
                re_ok, re_reason = is_location_eligible(re_probe, profile)
                if not re_ok:
                    existing.status = "rejected"
                    existing.reject_reasons = [re_reason or "location_not_eligible"]
                    continue
                if posted and (not existing.posted_at or posted > existing.posted_at):
                    existing.posted_at = posted
                persisted.append(existing)
                continue

            meta = dict(ingest.metadata or {})
            if posted:
                meta["posted_at"] = posted.isoformat()
            is_remote = meta.get("is_remote") or bool(
                re.search(r"\bremote\b", f"{ingest.title} {ingest.location or ''}", re.I)
            )
            if meta.get("is_internship") is None:
                meta["is_internship"] = bool(
                    re.search(r"\bintern(ship)?\b|\bapprentice\b|\bnew grad\b", ingest.title, re.I)
                )
            text = f"{ingest.title} {ingest.raw_description or ''} {ingest.location or ''}".lower()
            offers_sponsorship = infer_offers_sponsorship(text, meta)
            if offers_sponsorship is True:
                meta["visa_sponsorship"] = True
            elif offers_sponsorship is False:
                meta["visa_sponsorship"] = False
            job = Job(
                external_id=ingest.external_id[:256],
                source=ingest.source,
                title=ingest.title[:512],
                url=ingest.url[:2048],
                company_name=(ingest.company_name or "")[:256] or None,
                location=(ingest.location or "")[:256] or None,
                is_remote=is_remote,
                offers_sponsorship=offers_sponsorship,
                raw_description=ingest.raw_description,
                parsed_metadata=meta,
                discovered_at=datetime.now(timezone.utc),
                posted_at=posted,
                status="discovered",
            )
            self._session.add(job)
            persisted.append(job)
        await self._session.flush()
        return persisted
