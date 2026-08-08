from job_os.agents.base import BaseAgent
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext


class TrackingAgent(BaseAgent):
    """Application pipeline metrics and state summary."""

    name = "tracking"
    version = "0.2.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        applications = ctx.scratchpad.get("applications", [])
        browser_results = ctx.scratchpad.get("browser_apply_results", [])
        metrics = {
            "discovered": len(ctx.scratchpad.get("discovered_job_ids", [])),
            "qualified": len(ctx.scratchpad.get("qualified_job_ids", [])),
            "ranked": len(ctx.scratchpad.get("ranked_jobs", [])),
            "tailored_resumes": len(ctx.scratchpad.get("tailored_resumes", [])),
            "cover_letters": len(ctx.scratchpad.get("cover_letters", [])),
            "applications_draft": len(applications),
            "browser_apply_attempted": len(browser_results),
            "browser_apply_success": sum(1 for r in browser_results if r.get("success")),
        }
        ctx.scratchpad["session_metrics"] = metrics

        await self._emit(ctx, msg, "tracking.session_metrics", metrics)

        return AgentResult(
            success=True,
            output={"metrics": metrics, "applications": applications},
            next_step_hint="reflection",
        )
