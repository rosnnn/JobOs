"""Playwright form execution — dynamic fill, upload, optional submit."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from job_os.browser.form_audit import FormAuditReport
from job_os.browser.form_reasoner import FieldAnswer, FormPlan, FormReasoner


@dataclass
class ApplyResult:
    success: bool
    status: str
    page_url: str = ""
    error: str | None = None
    screenshots: list[bytes] = field(default_factory=list)
    html_snapshots: list[str] = field(default_factory=list)
    fields_filled: int = 0
    submitted: bool = False
    ats: str = "generic"
    form_audit: dict | None = None


class PlaywrightExecutor:
    def __init__(self, *, headless: bool = True, slow_mo_ms: int = 50):
        self._headless = headless
        self._slow_mo = slow_mo_ms
        self._reasoner = FormReasoner()

    async def apply_to_job(
        self,
        *,
        job_url: str,
        profile: dict[str, Any],
        resume_path: str | None,
        cover_letter: str | None,
        dry_run: bool = True,
        timeout_ms: int = 60_000,
    ) -> ApplyResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            return ApplyResult(
                success=False,
                status="failed",
                error=f"playwright not installed: {exc}",
            )

        ats = self._reasoner.detect_ats(job_url)
        audit = FormAuditReport(ats=ats)
        result = ApplyResult(success=False, status="running", ats=ats)
        total_filled = 0

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless, slow_mo=self._slow_mo)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            try:
                await page.goto(job_url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(2000)

                await self._click_apply_if_needed(page)
                captcha_type = await self._detect_captcha(page)
                if captcha_type:
                    audit.captcha_detected = True
                    audit.captcha_type = captcha_type
                    audit.stopped_reason = "captcha_requires_human"
                    audit.add(
                        page_index=0,
                        page_url=page.url,
                        label="Security verification (CAPTCHA)",
                        field_type="captcha",
                        required=True,
                        status="captcha",
                        notes="Complete CAPTCHA manually in browser — automation cannot bypass this.",
                    )
                    result.screenshots.append(await page.screenshot(full_page=True))
                    result.status = "awaiting_captcha"
                    result.error = f"captcha_detected:{captcha_type}"
                    result.form_audit = audit.summary()
                    result.page_url = page.url
                    return result

                await self._handle_signup_if_needed(page, profile)
                if "sign" in page.url.lower() or "register" in page.url.lower():
                    audit.account_signup_required = True

                for page_idx in range(6):
                    captcha_type = await self._detect_captcha(page)
                    if captcha_type:
                        audit.captcha_detected = True
                        audit.captcha_type = captcha_type
                        audit.stopped_reason = "captcha_mid_flow"
                        result.status = "awaiting_captcha"
                        result.error = f"captcha_detected:{captcha_type}"
                        break

                    dom_fields = await self._extract_fields(page)
                    plan = self._reasoner.plan(
                        dom_fields=dom_fields,
                        profile=profile,
                        cover_letter=cover_letter,
                        resume_path=resume_path,
                    )
                    filled = await self._execute_plan(page, plan, resume_path)
                    total_filled += filled

                    for raw in dom_fields:
                        label = (raw.get("label") or raw.get("name") or raw.get("id") or "").strip()
                        if not label and not raw.get("name"):
                            continue
                        hint = (raw.get("id") or raw.get("name") or label).lower()
                        ans = next(
                            (
                                a
                                for a in plan.fields
                                if a.selector_hint.lower() == hint
                                or a.selector_hint.lower() in hint
                                or hint in a.selector_hint.lower()
                            ),
                            None,
                        )
                        audit.add(
                            page_index=page_idx,
                            page_url=page.url,
                            label=label,
                            field_type=raw.get("type") or raw.get("tag", "text"),
                            required=bool(raw.get("required")),
                            status="filled" if ans else "skipped",
                            value=ans.value if ans else None,
                            notes=None if ans else "No matching answer in profile questionnaire",
                        )

                    result.screenshots.append(await page.screenshot(full_page=True))
                    result.html_snapshots.append(await page.content())
                    result.page_url = page.url

                    if not dry_run and await self._submit_form(page, ats):
                        result.submitted = True
                        result.status = "submitted"
                        result.success = True
                        break

                    if await self._click_next_page(page):
                        await page.wait_for_timeout(1500)
                        continue
                    break

                result.fields_filled = total_filled
                result.form_audit = audit.summary()

                if result.status == "awaiting_captcha":
                    result.success = total_filled > 0
                elif dry_run:
                    if total_filled > 0:
                        result.success = True
                        result.status = "dry_run_complete"
                    elif not audit.pages:
                        result.success = True
                        result.status = "dry_run_no_form"
                        result.error = "no_apply_form_on_page"
                    else:
                        result.success = True
                        result.status = "dry_run_partial"
                        result.error = "some_fields_unmatched"
                    result.submitted = False
                elif not result.submitted:
                    result.success = total_filled > 0
                    result.status = "submit_not_found" if total_filled else "apply_failed"

            except Exception as exc:
                result.success = False
                result.status = "failed"
                result.error = str(exc)
                result.form_audit = audit.summary()
                try:
                    result.screenshots.append(await page.screenshot(full_page=True))
                except Exception:
                    pass
            finally:
                await context.close()
                await browser.close()

        return result

    async def _detect_captcha(self, page) -> str | None:
        try:
            html = (await page.content()).lower()
            if "recaptcha" in html or "g-recaptcha" in html:
                return "recaptcha"
            if "hcaptcha" in html:
                return "hcaptcha"
            if "cloudflare" in html and ("challenge" in html or "turnstile" in html):
                return "cloudflare"
            if await page.locator("iframe[src*='recaptcha']").count() > 0:
                return "recaptcha"
            if await page.locator("iframe[src*='hcaptcha']").count() > 0:
                return "hcaptcha"
        except Exception:
            pass
        return None

    async def _click_next_page(self, page) -> bool:
        patterns = [
            re.compile(r"^next$", re.I),
            re.compile(r"continue", re.I),
            re.compile(r"save and continue", re.I),
            re.compile(r"proceed", re.I),
        ]
        for pat in patterns:
            for role in ("button", "link"):
                try:
                    loc = page.get_by_role(role, name=pat)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=5000)
                        return True
                except Exception:
                    pass
        return False

    async def _click_apply_if_needed(self, page) -> None:
        patterns = [
            re.compile(r"apply now", re.I),
            re.compile(r"apply for", re.I),
            re.compile(r"apply", re.I),
            re.compile(r"submit application", re.I),
            re.compile(r"i.?m interested", re.I),
        ]
        for pat in patterns:
            for role in ("link", "button"):
                try:
                    loc = page.get_by_role(role, name=pat)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=8000)
                        await page.wait_for_timeout(2500)
                        return
                except Exception:
                    pass
        # Job boards: follow external apply links
        try:
            for sel in (
                "a[href*='greenhouse.io']",
                "a[href*='lever.co']",
                "a[href*='workday']",
                "a[href*='apply']",
                "a[href*='ashby']",
            ):
                loc = page.locator(sel)
                if await loc.count() > 0:
                    await loc.first.click(timeout=8000)
                    await page.wait_for_timeout(2500)
                    return
        except Exception:
            pass

    async def _handle_signup_if_needed(self, page, profile: dict[str, Any]) -> None:
        """Click register/sign-in links and fill account creation when portal requires login."""
        signup_patterns = [
            re.compile(r"sign up", re.I),
            re.compile(r"register", re.I),
            re.compile(r"create account", re.I),
            re.compile(r"apply with email", re.I),
        ]
        for pat in signup_patterns:
            try:
                for role in ("link", "button"):
                    loc = page.get_by_role(role, name=pat)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=4000)
                        await page.wait_for_timeout(1500)
                        dom_fields = await self._extract_fields(page)
                        plan = self._reasoner.plan(dom_fields=dom_fields, profile=profile)
                        await self._execute_plan(page, plan, None)
                        return
            except Exception:
                pass

    async def _extract_fields(self, page) -> list[dict]:
        return await page.evaluate(
            """() => {
            const out = [];
            document.querySelectorAll('input, textarea, select').forEach(el => {
                if (el.type === 'hidden') return;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return;
                let label = '';
                if (el.labels && el.labels.length) label = el.labels[0].innerText;
                else if (el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
                else if (el.placeholder) label = el.placeholder;
                out.push({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    label: (label || '').trim(),
                    required: el.required || false,
                });
            });
            return out;
        }"""
        )

    async def _execute_plan(self, page, plan: FormPlan, resume_path: str | None) -> int:
        filled = 0
        for answer in plan.fields:
            try:
                if answer.action == "upload" and resume_path and Path(resume_path).exists():
                    locator = await self._resolve_field(page, answer.selector_hint)
                    if locator:
                        await locator.set_input_files(resume_path)
                        filled += 1
                    continue

                locator = await self._resolve_field(page, answer.selector_hint)
                if not locator:
                    continue

                if answer.action == "select":
                    await locator.select_option(label=answer.value)
                    filled += 1
                elif answer.action == "check":
                    if answer.value.lower() in ("yes", "true", "1"):
                        await locator.check()
                    filled += 1
                else:
                    await locator.fill(answer.value)
                    filled += 1
            except Exception:
                continue
        return filled

    async def _resolve_field(self, page, hint: str):
        if not hint:
            return None
        for strategy in (
            lambda: page.locator(f"#{hint}"),
            lambda: page.locator(f"[name='{hint}']"),
            lambda: page.get_by_label(re.compile(re.escape(hint[:40]), re.I)),
        ):
            try:
                loc = strategy()
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                continue
        return None

    async def _submit_form(self, page, ats: str) -> bool:
        await page.wait_for_timeout(1000)
        patterns = [
            re.compile(r"submit application", re.I),
            re.compile(r"submit", re.I),
            re.compile(r"apply", re.I),
        ]
        for pat in patterns:
            try:
                btn = page.get_by_role("button", name=pat)
                if await btn.count() > 0:
                    await btn.first.click(timeout=8000)
                    await page.wait_for_timeout(3000)
                    return True
            except Exception:
                continue
        return False
