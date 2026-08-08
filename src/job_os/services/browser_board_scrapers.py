"""Browser-based board scrapers with human-like pacing (LinkedIn, Wellfound)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlunparse

from job_os.config import get_settings
from job_os.schemas.jobs import JobIngest
from job_os.services.credentials_service import CredentialsService
from job_os.services.job_role_filter import is_software_engineering_role, normalize_job_title
from job_os.services.job_url_quality import is_real_job_posting
from job_os.services.location_eligibility import infer_offers_sponsorship, is_location_eligible
from job_os.services.profile_service import ProfileService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _board_state_path() -> Path:
    settings = get_settings()
    root = _artifact_root(settings) / "board_sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root / "state.json"


def _board_storage_state_file(board: str) -> Path:
    settings = get_settings()
    root = _artifact_root(settings) / "board_sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{board}_storage_state.json"


def _artifact_root(settings) -> Path:
    root = Path(settings.artifact_path)
    if root.is_absolute():
        return root
    project_root = Path(__file__).resolve().parents[3]
    return (project_root / root).resolve()


def _load_board_state() -> dict:
    path = _board_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_board_state(state: dict) -> None:
    path = _board_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _get_board_entry(board: str) -> dict:
    state = _load_board_state()
    return dict((state.get(board) or {}))


def board_scrape_state(board: str) -> dict:
    return _get_board_entry(board)


def board_scrape_snapshot() -> dict:
    state = _load_board_state()
    return {
        "linkedin": dict(state.get("linkedin") or {}),
        "wellfound": dict(state.get("wellfound") or {}),
    }


def _update_board_entry(board: str, **fields) -> None:
    state = _load_board_state()
    entry = dict(state.get(board) or {})
    entry.update(fields)
    state[board] = entry
    _save_board_state(state)


def _cooldown_active(board: str) -> bool:
    settings = get_settings()
    minutes = max(1, int(settings.browser_board_cooldown_minutes))
    cutoff = _utc_now() - timedelta(minutes=minutes)
    entry = _get_board_entry(board)
    last_scrape = _parse_iso(entry.get("last_scrape_at"))
    return bool(last_scrape and last_scrape >= cutoff)


def _relogin_allowed(board: str) -> bool:
    settings = get_settings()
    minutes = max(1, int(settings.browser_board_cooldown_minutes))
    cutoff = _utc_now() - timedelta(minutes=minutes)
    entry = _get_board_entry(board)
    last_login = _parse_iso(entry.get("last_login_at"))
    return not last_login or last_login < cutoff


def _mark_scrape(board: str, *, status: str, count: int) -> None:
    _update_board_entry(
        board,
        last_scrape_at=_to_iso(_utc_now()),
        last_status=status,
        last_result_count=count,
    )


def _mark_login(board: str) -> None:
    _update_board_entry(board, last_login_at=_to_iso(_utc_now()))


async def _needs_linkedin_login(page) -> bool:
    try:
        await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded", timeout=45_000)
    except Exception:
        return True
    url = (page.url or "").lower()
    if "/login" in url or "checkpoint" in url:
        return True
    try:
        return await page.locator("#username").count() > 0
    except Exception:
        return False


async def _needs_wellfound_login(page) -> bool:
    try:
        await page.goto("https://wellfound.com/jobs", wait_until="domcontentloaded", timeout=45_000)
    except Exception:
        return True
    url = (page.url or "").lower()
    if "/login" in url or "sign_in" in url:
        return True
    try:
        return await page.locator("input[name='email']").count() > 0
    except Exception:
        return False


def _probe(title: str, desc: str, loc: str, source: str, meta: dict, sponsor: bool | None = None):
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


def _to_ingest(
    *,
    source: str,
    title: str,
    url: str,
    company: str | None,
    location: str,
    description: str,
    metadata: dict,
    profile: dict,
) -> JobIngest | None:
    title = normalize_job_title(title)
    if not title:
        return None
    role_ok, _ = is_software_engineering_role(title, description)
    if not role_ok:
        return None
    real, _ = is_real_job_posting(url, source=source, title=title)
    if not real:
        return None

    text = f"{title} {description} {location}".lower()
    sponsor = infer_offers_sponsorship(text, metadata)
    if sponsor is True:
        metadata["visa_sponsorship"] = True
    elif sponsor is False:
        metadata["visa_sponsorship"] = False

    # Do not reject by location here: apply-page enrichment + central persist filter can decide with fuller context.
    canonical_url = _canonical_job_url(url)
    ext = hashlib.sha256(f"{source}:{canonical_url}".encode("utf-8")).hexdigest()[:24]
    return JobIngest(
        external_id=ext,
        source=source,
        title=title,
        url=canonical_url,
        company_name=company,
        location=location,
        raw_description=description,
        metadata=metadata,
    )


def _canonical_job_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()
        path = parsed.path
        query = ""
        if "linkedin.com" in host:
            # Keep only stable path; drop tracking/search query params.
            query = ""
        elif "wellfound.com" in host:
            query = ""
        return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))
    except Exception:
        return url


async def _human_delay() -> None:
    s = get_settings()
    lo = max(250, s.browser_board_min_delay_ms)
    hi = max(lo + 50, s.browser_board_max_delay_ms)
    await asyncio.sleep(random.uniform(lo / 1000, hi / 1000))


async def _scroll_safely(page, scrolls: int) -> None:
    for _ in range(scrolls):
        await page.mouse.wheel(0, random.randint(500, 1100))
        await _human_delay()


async def discover_linkedin_browser(seeds: list[dict]) -> list[JobIngest]:
    """Login to LinkedIn and scrape jobs with slow scrolling and delays."""
    settings = get_settings()
    board = "linkedin"
    if _cooldown_active(board):
        _mark_scrape(board, status="cooldown_skip", count=0)
        return []
    creds = CredentialsService().load()
    linkedin_email = creds.get("linkedin_email") or settings.linkedin_email
    linkedin_password = creds.get("linkedin_password") or settings.linkedin_password
    if not linkedin_email or not linkedin_password:
        _mark_scrape(board, status="missing_credentials", count=0)
        return []

    profile = ProfileService().load()
    queries = [s.get("q") for s in seeds if s.get("q")]
    if not queries:
        queries = ["software engineer", "backend engineer", "software engineer intern"]
    queries = [q for q in queries if str(q).strip()]
    queries = list(dict.fromkeys(queries))[: max(1, settings.browser_board_max_queries)]

    out: list[JobIngest] = []
    seen: set[str] = set()

    try:
        from playwright.async_api import TimeoutError as PwTimeout
        from playwright.async_api import async_playwright
    except Exception:
        _mark_scrape(board, status="playwright_unavailable", count=0)
        return []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=settings.browser_headless,
            slow_mo=max(0, settings.browser_board_slow_mo_ms),
        )
        state_file = _board_storage_state_file(board)
        context = (
            await browser.new_context(storage_state=str(state_file))
            if state_file.exists()
            else await browser.new_context()
        )
        page = await context.new_page()

        try:
            if await _needs_linkedin_login(page):
                if not _relogin_allowed(board):
                    _mark_scrape(board, status="relogin_cooldown_skip", count=0)
                    await browser.close()
                    return []
                await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60_000)
                await _human_delay()
                await page.fill("#username", linkedin_email)
                await _human_delay()
                await page.fill("#password", linkedin_password)
                await _human_delay()
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle", timeout=60_000)
                await context.storage_state(path=str(state_file))
                _mark_login(board)
        except PwTimeout:
            _mark_scrape(board, status="login_timeout", count=0)
            await browser.close()
            return []

        for query in queries:
            search_url = (
                "https://www.linkedin.com/jobs/search/?keywords="
                f"{quote_plus(query)}&f_TPR=r604800&position=1&pageNum=0"
            )
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                await _human_delay()
                await _scroll_safely(page, settings.browser_board_max_scrolls)
            except PwTimeout:
                continue

            cards = page.locator(
                "li.jobs-search-results__list-item, div.job-card-container, ul.jobs-search__results-list li"
            )
            count = min(await cards.count(), settings.browser_board_max_cards_per_query)
            for idx in range(count):
                card = cards.nth(idx)
                try:
                    link = card.locator("a").first
                    href = (await link.get_attribute("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = f"https://www.linkedin.com{href}"
                    if href in seen:
                        continue
                    seen.add(href)

                    title = (await card.inner_text(timeout=3_000)).split("\n")[0].strip()
                    company = None
                    location = ""
                    try:
                        company = (await card.locator(".job-card-container__company-name, h4 a, .base-search-card__subtitle a").first.inner_text(timeout=2_000)).strip()
                    except Exception:
                        pass
                    try:
                        location = (await card.locator(".job-card-container__metadata-item, .job-search-card__location").first.inner_text(timeout=2_000)).strip()
                    except Exception:
                        location = ""

                    await card.click(timeout=4_000)
                    await _human_delay()
                    desc = ""
                    try:
                        desc = (
                            await page.locator(
                                "div.jobs-description-content__text, div.show-more-less-html__markup"
                            )
                            .first.inner_text(timeout=2_000)
                        ).strip()
                    except Exception:
                        desc = ""

                    meta = {
                        "is_remote": "remote" in f"{title} {location} {desc}".lower(),
                        "board_family": "linkedin_direct",
                        "slow_scrape": True,
                        "query": query,
                    }
                    row = _to_ingest(
                        source="linkedin",
                        title=title,
                        url=href,
                        company=company,
                        location=location,
                        description=desc,
                        metadata=meta,
                        profile=profile,
                    )
                    if row:
                        out.append(row)
                except Exception:
                    continue

        await browser.close()
    _mark_scrape(board, status="ok", count=len(out))
    return out


async def discover_wellfound_browser(seeds: list[dict]) -> list[JobIngest]:
    """Login to Wellfound and scrape job cards with pacing to reduce bot risk."""
    settings = get_settings()
    board = "wellfound"
    if _cooldown_active(board):
        _mark_scrape(board, status="cooldown_skip", count=0)
        return []
    creds = CredentialsService().load()
    wellfound_email = creds.get("wellfound_email") or settings.wellfound_email
    wellfound_password = creds.get("wellfound_password") or settings.wellfound_password
    if not wellfound_email or not wellfound_password:
        _mark_scrape(board, status="missing_credentials", count=0)
        return []

    profile = ProfileService().load()
    queries = [s.get("q") for s in seeds if s.get("q")]
    if not queries:
        queries = ["software engineer", "backend engineer", "intern"]
    queries = [q for q in queries if str(q).strip()]
    queries = list(dict.fromkeys(queries))[: max(1, settings.browser_board_max_queries)]

    out: list[JobIngest] = []
    seen: set[str] = set()

    try:
        from playwright.async_api import TimeoutError as PwTimeout
        from playwright.async_api import async_playwright
    except Exception:
        _mark_scrape(board, status="playwright_unavailable", count=0)
        return []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=settings.browser_headless,
            slow_mo=max(0, settings.browser_board_slow_mo_ms),
        )
        state_file = _board_storage_state_file(board)
        context = (
            await browser.new_context(storage_state=str(state_file))
            if state_file.exists()
            else await browser.new_context()
        )
        page = await context.new_page()

        try:
            if await _needs_wellfound_login(page):
                if not _relogin_allowed(board):
                    _mark_scrape(board, status="relogin_cooldown_skip", count=0)
                    await browser.close()
                    return []
                await page.goto("https://wellfound.com/login", wait_until="domcontentloaded", timeout=60_000)
                await _human_delay()
                await page.fill("input[name='email']", wellfound_email)
                await _human_delay()
                await page.fill("input[name='password']", wellfound_password)
                await _human_delay()
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle", timeout=60_000)
                await context.storage_state(path=str(state_file))
                _mark_login(board)
        except PwTimeout:
            _mark_scrape(board, status="login_timeout", count=0)
            await browser.close()
            return []

        for query in queries:
            url = f"https://wellfound.com/jobs?query={quote_plus(query)}"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await _human_delay()
                await _scroll_safely(page, settings.browser_board_max_scrolls)
            except PwTimeout:
                continue

            # Wellfound UI changes often; keep selectors broad and strict on URL quality later.
            cards = page.locator("a[href*='/jobs/']")
            count = min(await cards.count(), settings.browser_board_max_cards_per_query)
            for idx in range(count):
                link = cards.nth(idx)
                try:
                    href = (await link.get_attribute("href") or "").strip()
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = f"https://wellfound.com{href}"
                    if href in seen:
                        continue
                    seen.add(href)

                    text = (await link.inner_text(timeout=2_000)).strip()
                    if len(text) < 6:
                        continue
                    title = re.split(r"\s{2,}|\n", text)[0].strip()
                    company = None
                    location = ""

                    await link.click(timeout=4_000)
                    await _human_delay()
                    desc = ""
                    try:
                        desc = (await page.locator("main").first.inner_text(timeout=3_000)).strip()[:8000]
                    except Exception:
                        desc = ""

                    meta = {
                        "is_remote": "remote" in f"{title} {desc}".lower(),
                        "board_family": "wellfound_direct",
                        "slow_scrape": True,
                        "query": query,
                    }
                    row = _to_ingest(
                        source="wellfound",
                        title=title,
                        url=href,
                        company=company,
                        location=location,
                        description=desc,
                        metadata=meta,
                        profile=profile,
                    )
                    if row:
                        out.append(row)

                    await page.go_back(wait_until="domcontentloaded", timeout=30_000)
                    await _human_delay()
                except Exception:
                    continue

        await browser.close()

    _mark_scrape(board, status="ok", count=len(out))

    return out
