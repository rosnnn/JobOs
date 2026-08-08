from uuid import UUID

from sqlalchemy import select

from job_os.agents.base import BaseAgent
from job_os.models.application import Application
from job_os.models.browser import ApprovalRequest
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.services.application_service import ApplicationService


class AutoApproveAgent(BaseAgent):
    """Auto-approve pending applications for autonomous auto-apply runs."""

    name = "auto_approve"
    version = "0.1.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        app_svc = ApplicationService(self._session)
        app_ids = ctx.scratchpad.get("application_ids_to_submit", [])

        if not app_ids:
            stmt = select(Application).where(
                Application.approval_status == "pending",
                Application.status == "draft",
            )
            result = await self._session.execute(stmt)
            apps = list(result.scalars().all())
            app_ids = [str(a.id) for a in apps]

        approved: list[str] = []
        for app_id_str in app_ids:
            app = await app_svc.approve_application(UUID(app_id_str), decided_by="auto_approve_agent")
            if app:
                approved.append(app_id_str)

        ctx.scratchpad["application_ids_to_submit"] = approved

        await self._emit(ctx, msg, "auto_approve.completed", {"approved": len(approved)})

        return AgentResult(
            success=True,
            output={"approved_count": len(approved), "application_ids": approved},
            next_step_hint="browser_apply",
        )
