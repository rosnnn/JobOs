"""Orchestrates a single application through browser automation."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from job_os.browser.apply_url import assess_apply_url
from job_os.browser.executor import PlaywrightExecutor
from job_os.browser.rate_limit import RateLimitService
from job_os.browser.session import BrowserSessionManager
from job_os.config import get_settings
from job_os.models.application import Application
from job_os.models.identity import CoverLetter, Resume
from job_os.models.job import Job
from job_os.services.application_data import merge_application_profile
from job_os.services.profile_service import ProfileService


class BrowserApplyService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._settings = get_settings()
        self._sessions = BrowserSessionManager(session)
        self._rate_limit = RateLimitService(session)

    async def apply_application(
        self,
        application_id: UUID,
        *,
        dry_run: bool | None = None,
        force: bool = False,
        playwright_timeout_ms: int = 60_000,
    ) -> dict:
        app = await self._session.get(Application, application_id)
        if not app:
            return {"success": False, "error": "application_not_found"}

        use_dry_run = self._settings.browser_dry_run if dry_run is None else dry_run

        if app.approval_status != "approved" and not force:
            if (
                self._settings.require_approval_for_apply
                and self._settings.is_supervised
                and not use_dry_run
            ):
                return {
                    "success": False,
                    "error": "approval_required",
                    "approval_status": app.approval_status,
                }

        job = await self._session.get(Job, app.job_id)
        if not job:
            return {"success": False, "error": "job_not_found", "status": "apply_failed"}

        can_auto, url_msg = assess_apply_url(job.url, job.source, title=job.title or "")
        if not can_auto:
            app.status = "not_applyable"
            app.metadata_ = {**(app.metadata_ or {}), "last_error": url_msg, "apply_note": url_msg}
            await self._session.flush()
            return {
                "success": False,
                "application_id": str(application_id),
                "status": "not_applyable",
                "error": url_msg,
                "user_message": url_msg,
                "fields_filled": 0,
                "dry_run": use_dry_run,
            }

        can_apply, limit_reason = await self._rate_limit.check_can_apply(source=job.source)
        if not can_apply:
            return {"success": False, "error": limit_reason}

        resume = await self._session.get(Resume, app.resume_id) if app.resume_id else None
        cover = await self._session.get(CoverLetter, app.cover_letter_id) if app.cover_letter_id else None
        profile = merge_application_profile(ProfileService().load())

        resume_path = resume.content_path if resume and resume.content_path else None
        if resume_path and not Path(resume_path).exists() and resume and resume.content_text:
            resume_path = await self._materialize_resume_file(application_id, resume.content_text)

        # Prefer uploaded PDF from resume/ folder for ATS uploads
        pdf_path = self._find_source_pdf()
        if pdf_path:
            resume_path = pdf_path

        browser_session = await self._sessions.create_session(job_url=job.url)
        browser_session.status = "running"
        app.browser_session_id = browser_session.id
        app.status = "applying"
        await self._session.flush()

        executor = PlaywrightExecutor(headless=self._settings.browser_headless)
        result = await executor.apply_to_job(
            job_url=job.url,
            profile=profile,
            resume_path=resume_path,
            cover_letter=cover.content_text if cover else None,
            dry_run=use_dry_run,
            timeout_ms=playwright_timeout_ms,
        )

        for i, shot in enumerate(result.screenshots):
            await self._sessions.save_artifact(
                browser_session.id,
                f"screenshot_{i}",
                shot,
                suffix=".png",
            )

        if result.html_snapshots:
            await self._sessions.save_artifact(
                browser_session.id,
                "html_final",
                result.html_snapshots[-1].encode("utf-8"),
                suffix=".html",
            )

        browser_session.ended_at = datetime.now(timezone.utc)
        browser_session.metadata_ = {
            "ats": result.ats,
            "fields_filled": result.fields_filled,
            "submitted": result.submitted,
            "dry_run": use_dry_run,
            "page_url": result.page_url,
            "form_audit": result.form_audit,
        }

        listing_only = result.status in ("dry_run_no_form", "dry_run_listing_only", "dry_run_partial")
        captcha_blocked = result.status == "awaiting_captcha"

        if result.success or captcha_blocked:
            browser_session.status = result.status
            app.metadata_ = {
                **(app.metadata_ or {}),
                "applied_company": job.company_name,
                "applied_job_title": job.title,
                "applied_to_email_domain": (job.company_name or "").lower().replace(" ", ""),
            }
            if listing_only:
                app.status = "dry_run_complete"
                app.metadata_["apply_note"] = result.error or result.status
                app.metadata_["listing_only"] = True
            elif captcha_blocked:
                app.status = "awaiting_captcha"
                app.metadata_["captcha_type"] = (result.form_audit or {}).get("captcha_type")
                app.metadata_["apply_note"] = (
                    "CAPTCHA detected — open the job URL in your browser, complete verification, "
                    "then finish the form manually or retry Real submit."
                )
            elif result.submitted:
                app.applied_at = datetime.now(timezone.utc)
                app.status = "submitted"
                job.status = "applied"
                await self._rate_limit.record_apply(source=job.source)
            else:
                app.status = result.status if use_dry_run else "ready_to_submit"
            if result.form_audit:
                app.metadata_["form_audit"] = result.form_audit
        else:
            browser_session.status = "failed"
            browser_session.error_message = result.error
            app.status = result.status if result.status in ("submit_not_found", "failed") else "apply_failed"
            app.metadata_ = {
                **(app.metadata_ or {}),
                "last_error": result.error or result.status,
                "apply_note": result.error,
            }
            if result.form_audit:
                app.metadata_["form_audit"] = result.form_audit

        await self._session.flush()

        user_message = self._build_user_message(
            success=result.success or captcha_blocked,
            status=app.status,
            dry_run=use_dry_run,
            fields_filled=result.fields_filled,
            error=result.error,
            apply_note=(app.metadata_ or {}).get("apply_note"),
            listing_only=listing_only,
            form_audit=result.form_audit,
        )

        return {
            "success": result.success or captcha_blocked,
            "application_id": str(application_id),
            "browser_session_id": str(browser_session.id),
            "status": app.status,
            "fields_filled": result.fields_filled,
            "submitted": result.submitted,
            "dry_run": use_dry_run,
            "ats": result.ats,
            "error": result.error,
            "skipped": listing_only,
            "apply_note": (app.metadata_ or {}).get("apply_note"),
            "user_message": user_message,
            "form_audit": result.form_audit,
        }

    @staticmethod
    def _build_user_message(
        *,
        success: bool,
        status: str,
        dry_run: bool,
        fields_filled: int,
        error: str | None,
        apply_note: str | None,
        listing_only: bool,
        form_audit: dict | None = None,
    ) -> str:
        if status == "awaiting_captcha":
            ctype = (form_audit or {}).get("captcha_type", "unknown")
            filled = (form_audit or {}).get("filled", 0)
            return (
                f"CAPTCHA ({ctype}) — automation paused. Filled {filled} field(s) before stop. "
                "Complete verification in browser, then finish manually or retry."
            )
        if status == "not_applyable":
            return error or apply_note or "This job cannot be auto-applied."
        if success and dry_run:
            if fields_filled > 0:
                audit_note = ""
                if form_audit:
                    audit_note = (
                        f" ({form_audit.get('filled', 0)} matched in report, "
                        f"{form_audit.get('skipped', 0)} skipped)"
                    )
                return (
                    f"Dry-run OK — filled {fields_filled} field(s){audit_note}. "
                    "See Form fill report below. Use Real submit on direct ATS links."
                )
            if listing_only:
                return (
                    "Dry-run: page opened but no application form found. "
                    "This is a job description page — click View job posting, find Apply, "
                    "or pick Greenhouse/Lever/Himalayas roles with direct apply links."
                )
            return "Dry-run OK — no form fields detected on this page."
        if success and status == "submitted":
            return "Application submitted successfully."
        if success:
            return f"Ready to submit ({fields_filled} fields filled)."
        if status == "submit_not_found":
            return (
                "Could not find a Submit button. "
                "Complete the form manually on the company site, or use a direct ATS apply link."
            )
        return error or f"Apply failed ({status})."

    def _find_source_pdf(self) -> str | None:
        resume_dir = self._settings.source_resume_dir
        if not resume_dir.exists():
            return None
        pdfs = sorted(resume_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        return str(pdfs[0]) if pdfs else None

    async def _materialize_resume_file(self, application_id: UUID, content: str) -> str:
        settings = get_settings()
        out_dir = Path(settings.artifact_path) / "resumes" / str(application_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "resume_for_upload.md"
        path.write_text(content, encoding="utf-8")
        return str(path)
