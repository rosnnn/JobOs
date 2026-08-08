import asyncio
from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.browser.apply_service import BrowserApplyService
from job_os.config import get_settings
from job_os.models.application import Application
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext


class BrowserApplyAgent(BaseAgent):
    name = "browser_apply"
    version = "0.3.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        settings = get_settings()
        apply_svc = BrowserApplyService(self._session)
        results: list[dict] = []
        errors: list[str] = []

        application_ids = await self._resolve_application_ids(ctx, msg)

        if not application_ids:
            return AgentResult(
                success=True,
                output={"applied": 0, "message": "no_applications_to_submit"},
                next_step_hint="tracking",
            )

        limit = settings.max_browser_apply_per_run
        if ctx.workflow_type == "auto_apply_all":
            limit = settings.auto_apply_max_per_run
        prefs = ctx.scratchpad.get("job_preferences") or {}
        if prefs.get("auto_apply_max_per_run"):
            limit = int(prefs["auto_apply_max_per_run"])

        force = ctx.workflow_type == "auto_apply_all" and settings.auto_approve_on_auto_apply
        if "dry_run" in ctx.scratchpad:
            dry_run = bool(ctx.scratchpad["dry_run"])
        else:
            dry_run = settings.auto_apply_dry_run
            if dry_run is None:
                dry_run = settings.browser_dry_run

        fast_dry_run = bool(ctx.scratchpad.get("fast_dry_run")) and dry_run
        if ctx.scratchpad.get("max_apply") is not None:
            limit = min(limit, int(ctx.scratchpad["max_apply"]))
        delay_sec = 2 if fast_dry_run else settings.min_delay_between_applications_sec
        timeout_ms = 35_000 if fast_dry_run else 60_000

        for i, app_id in enumerate(application_ids[:limit]):
            if i > 0:
                await asyncio.sleep(delay_sec)
            try:
                outcome = await apply_svc.apply_application(
                    app_id,
                    dry_run=dry_run,
                    force=force,
                    playwright_timeout_ms=timeout_ms,
                )
                results.append(outcome)
                if not outcome.get("success"):
                    errors.append(f"{app_id}:{outcome.get('error')}")
            except Exception as exc:
                errors.append(f"{app_id}:{exc}")
                results.append({"success": False, "application_id": str(app_id), "error": str(exc)})

        ctx.scratchpad["browser_apply_results"] = results
        success_count = sum(1 for r in results if r.get("success"))

        await self._emit(
            ctx,
            msg,
            "browser_apply.completed",
            {
                "attempted": len(results),
                "success": success_count,
                "dry_run": settings.browser_dry_run,
                "errors": errors,
            },
        )

        skipped = sum(1 for r in results if r.get("skipped"))
        return AgentResult(
            success=success_count > 0 or skipped > 0 or len(results) == 0,
            output={
                "results": results,
                "success_count": success_count,
                "skipped_count": skipped,
                "errors": errors,
            },
            next_step_hint="tracking",
        )

    async def _resolve_application_ids(
        self,
        ctx: WorkflowContext,
        msg: AgentMessage,
    ) -> list[UUID]:
        if msg.payload.get("application_ids"):
            return [UUID(x) for x in msg.payload["application_ids"]]

        if ctx.scratchpad.get("application_ids_to_submit"):
            return [UUID(x) for x in ctx.scratchpad["application_ids_to_submit"]]

        # Approved applications from DB
        stmt = select(Application).where(
            Application.approval_status == "approved",
            Application.status.in_(("approved", "draft", "dry_run_complete")),
        )
        result = await self._session.execute(stmt)
        apps = list(result.scalars().all())

        if not apps and ctx.scratchpad.get("applications"):
            # Supervised: only submit explicitly approved in scratchpad
            approved_ids = [
                UUID(a["application_id"])
                for a in ctx.scratchpad["applications"]
                if a.get("submit_approved")
            ]
            return approved_ids

        return [app.id for app in apps]
