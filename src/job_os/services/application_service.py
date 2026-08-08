from uuid import UUID
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_os.models.application import Application
from job_os.models.browser import ApprovalRequest
from job_os.models.identity import CoverLetter, Resume
from job_os.models.job import Job
from job_os.services.job_dedup import job_fingerprint
from job_os.services.job_role_filter import is_software_engineering_role, normalize_job_title
from job_os.services.job_url_quality import is_real_job_record
from job_os.services.location_eligibility import is_location_eligible
from job_os.services.preferences_service import PreferencesService
from job_os.services.profile_service import ProfileService


class ApplicationService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_applications(
        self,
        *,
        status: str | None = None,
        approval_status: str | None = None,
        outcome: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_cancelled: bool = False,
    ) -> list[Application]:
        stmt = select(Application).order_by(Application.created_at.desc())
        if not include_cancelled:
            stmt = stmt.where(
                Application.status != "cancelled",
                Application.approval_status != "cancelled",
            )
        if status:
            stmt = stmt.where(Application.status == status)
        if approval_status:
            stmt = stmt.where(Application.approval_status == approval_status)
        if outcome:
            stmt = stmt.where(Application.outcome == outcome)
        stmt = stmt.limit(limit * 3).offset(offset)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return self._dedupe_by_job(rows)[:limit]

    @staticmethod
    def _dedupe_by_job(apps: list[Application]) -> list[Application]:
        """Keep only the newest application per job."""
        seen: dict = {}
        for app in apps:
            key = str(app.job_id)
            if key not in seen:
                seen[key] = app
        return list(seen.values())

    async def cancel_duplicate_applications(self, *, limit: int = 200) -> int:
        stmt = (
            select(Application)
            .where(Application.status != "cancelled")
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        seen_jobs: set = set()
        cancelled = 0
        for app in rows:
            jid = str(app.job_id)
            if jid in seen_jobs:
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {**(app.metadata_ or {}), "cancel_reason": ["duplicate_application"]}
                cancelled += 1
            else:
                seen_jobs.add(jid)
        await self._session.flush()
        return cancelled

    async def get_application(self, application_id: UUID) -> Application | None:
        result = await self._session.execute(
            select(Application).where(Application.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_resume(self, resume_id: UUID) -> Resume | None:
        result = await self._session.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalar_one_or_none()

    async def get_cover_letter(self, letter_id: UUID) -> CoverLetter | None:
        result = await self._session.execute(select(CoverLetter).where(CoverLetter.id == letter_id))
        return result.scalar_one_or_none()

    async def get_job_for_application(self, job_id: UUID) -> Job | None:
        result = await self._session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_pending_approvals(self, limit: int = 50) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def approve_application(self, application_id: UUID, *, decided_by: str = "operator") -> Application | None:
        app = await self.get_application(application_id)
        if not app:
            return None
        app.approval_status = "approved"
        app.status = "approved"

        all_pending = await self.list_pending_approvals(200)
        for req in all_pending:
            if req.payload.get("application_id") == str(application_id):
                req.status = "approved"
                from datetime import datetime, timezone

                req.decided_at = datetime.now(timezone.utc)
                req.decided_by = decided_by
        await self._session.flush()
        return app

    async def approve_all_pending(self, *, limit: int = 50, software_only: bool = True) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.approval_status == "pending", Application.status == "draft")
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        prefs_svc = PreferencesService()
        prefs = prefs_svc.load()
        approved: list[Application] = []
        for app in result.scalars().all():
            job = await self.get_job_for_application(app.job_id)
            if job:
                real, url_reason = is_real_job_record(job)
                if not real:
                    app.status = "cancelled"
                    app.approval_status = "cancelled"
                    app.metadata_ = {
                        **(app.metadata_ or {}),
                        "cancel_reason": ["not_real_job_posting", url_reason],
                    }
                    job.status = "rejected"
                    job.reject_reasons = [url_reason]
                    continue
            if software_only and job:
                ok, reasons = prefs_svc.matches_job(job, prefs)
                if not ok:
                    app.status = "cancelled"
                    app.approval_status = "cancelled"
                    app.metadata_ = {
                        **(app.metadata_ or {}),
                        "cancel_reason": reasons,
                    }
                    if job.status == "application_draft":
                        job.status = "rejected"
                        job.reject_reasons = reasons
                    continue
            updated = await self.approve_application(app.id, decided_by="bulk_approve")
            if updated:
                approved.append(updated)
        await self._session.flush()
        return approved

    async def purge_invalid_jobs_and_applications(self, *, limit: int = 500) -> dict:
        """Reject non-real postings and cancel their applications (listing pages, scraped junk)."""
        stmt = select(Job).limit(limit)
        result = await self._session.execute(stmt)
        jobs_rejected = 0
        apps_cancelled = 0
        for job in result.scalars().all():
            real, reason = is_real_job_record(job)
            role_ok, role_reason = is_software_engineering_role(
                normalize_job_title(job.title or ""),
                job.raw_description,
            )
            if real and role_ok:
                continue
            reject_reason = role_reason if real and not role_ok else reason
            job.status = "rejected"
            job.reject_reasons = [reject_reason]
            jobs_rejected += 1
            app_stmt = select(Application).where(Application.job_id == job.id)
            app_res = await self._session.execute(app_stmt)
            for app in app_res.scalars().all():
                if app.status in ("cancelled", "submitted"):
                    continue
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {
                    **(app.metadata_ or {}),
                    "cancel_reason": ["not_real_job_posting", reason],
                }
                apps_cancelled += 1
        # Cancel dry-run / listing-only applications (never real submissions)
        app_stmt = select(Application).where(
            Application.status.in_(
                ("draft", "approved", "dry_run_complete", "not_applyable", "apply_failed", "ready_to_submit")
            )
        ).limit(limit)
        app_res = await self._session.execute(app_stmt)
        for app in app_res.scalars().all():
            meta = app.metadata_ or {}
            if meta.get("listing_only") or meta.get("apply_note") == "listing_page_no_fillable_form":
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {
                    **meta,
                    "cancel_reason": ["listing_only_not_a_real_apply"],
                }
                apps_cancelled += 1

        await self._session.flush()
        return {
            "jobs_rejected": jobs_rejected,
            "applications_cancelled": apps_cancelled,
        }

    async def purge_location_ineligible_jobs(self) -> dict:
        """Reject jobs that fail location/visa rules for the current profile."""
        profile = ProfileService().load()
        prefs = PreferencesService().load()
        stmt = select(Job).where(
            Job.status.in_(("discovered", "qualified", "ranked", "application_draft"))
        )
        result = await self._session.execute(stmt)
        jobs_rejected = 0
        apps_cancelled = 0
        for job in result.scalars().all():
            ok, reason = is_location_eligible(job, profile, prefs)
            if ok:
                continue
            job.status = "rejected"
            job.reject_reasons = [reason or "location_not_eligible"]
            if job.offers_sponsorship and reason in ("foreign_country_only", "remote_country_locked", "country_restricted"):
                job.offers_sponsorship = False
            jobs_rejected += 1
            app_stmt = select(Application).where(Application.job_id == job.id)
            app_res = await self._session.execute(app_stmt)
            for app in app_res.scalars().all():
                if app.status in ("cancelled", "submitted"):
                    continue
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {
                    **(app.metadata_ or {}),
                    "cancel_reason": [reason or "location_not_eligible"],
                }
                apps_cancelled += 1
        await self._session.flush()
        return {"jobs_rejected": jobs_rejected, "applications_cancelled": apps_cancelled}

    async def purge_stale_jobs(self, *, max_age_days: int = 30, limit: int = 5000) -> dict:
        """Reject stale jobs and cancel pending drafts tied to them."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stmt = (
            select(Job)
            .where(Job.status.in_(("discovered", "qualified", "ranked", "application_draft", "rejected")))
            .order_by(Job.posted_at.asc().nullsfirst(), Job.discovered_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        stale_jobs = 0
        apps_cancelled = 0
        for job in result.scalars().all():
            pivot = job.posted_at or job.discovered_at or job.created_at
            if not pivot or pivot >= cutoff:
                continue
            if job.status != "rejected":
                job.status = "rejected"
                job.reject_reasons = ["stale_posting"]
                stale_jobs += 1

            app_stmt = select(Application).where(Application.job_id == job.id)
            app_res = await self._session.execute(app_stmt)
            for app in app_res.scalars().all():
                if app.status in ("submitted", "cancelled"):
                    continue
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {
                    **(app.metadata_ or {}),
                    "cancel_reason": ["stale_job_posting"],
                }
                apps_cancelled += 1

        await self._session.flush()
        return {"jobs_rejected": stale_jobs, "applications_cancelled": apps_cancelled}

    async def purge_duplicate_jobs(self, *, limit: int = 8000) -> dict:
        """Reject older duplicate jobs by company+title fingerprint and cancel pending apps on dupes."""
        stmt = (
            select(Job)
            .where(Job.status.in_(("discovered", "qualified", "ranked", "application_draft")))
            .order_by(Job.posted_at.desc().nullslast(), Job.discovered_at.desc().nullslast(), Job.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        keep_by_fp: dict[str, Job] = {}
        jobs_rejected = 0
        apps_cancelled = 0

        for job in rows:
            fp = job_fingerprint(job.company_name, job.title or "")
            keep = keep_by_fp.get(fp)
            if keep is None:
                keep_by_fp[fp] = job
                continue

            job.status = "rejected"
            job.reject_reasons = ["duplicate_posting"]
            jobs_rejected += 1

            app_stmt = select(Application).where(Application.job_id == job.id)
            app_res = await self._session.execute(app_stmt)
            for app in app_res.scalars().all():
                if app.status in ("submitted", "cancelled"):
                    continue
                app.status = "cancelled"
                app.approval_status = "cancelled"
                app.metadata_ = {**(app.metadata_ or {}), "cancel_reason": ["duplicate_job_posting"]}
                apps_cancelled += 1

        await self._session.flush()
        return {"jobs_rejected": jobs_rejected, "applications_cancelled": apps_cancelled}

    async def cancel_non_software_applications(self, *, limit: int = 100) -> int:
        """Cancel approved/draft apps that fail software/keyword filters."""
        prefs_svc = PreferencesService()
        prefs = prefs_svc.load()
        stmt = (
            select(Application)
            .where(
                Application.status.in_(("draft", "approved", "dry_run_complete", "apply_failed")),
                Application.approval_status.in_(("pending", "approved")),
            )
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        cancelled = 0
        for app in result.scalars().all():
            job = await self.get_job_for_application(app.job_id)
            if not job:
                continue
            ok, reasons = prefs_svc.matches_job(job, prefs)
            if ok:
                continue
            app.status = "cancelled"
            app.approval_status = "cancelled"
            app.metadata_ = {**(app.metadata_ or {}), "cancel_reason": reasons}
            job.status = "rejected"
            job.reject_reasons = reasons
            cancelled += 1
        await self._session.flush()
        return cancelled
