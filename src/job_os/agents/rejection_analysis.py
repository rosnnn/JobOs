from job_os.agents.base import BaseAgent
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext
from job_os.services.rejection_analyzer import RejectionAnalyzer
from job_os.world_model.service import WorldModelService


class RejectionAnalysisAgent(BaseAgent):
    name = "rejection_analysis"
    version = "0.1.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        analyzer = RejectionAnalyzer(self._session)
        analysis = await analyzer.analyze()
        fixed = await analyzer.apply_fixes_to_applications()

        world = WorldModelService(self._session)
        await world.merge_update(
            {"rejection_analysis": analysis, "last_rejection_analysis_at": str(__import__("datetime").datetime.utcnow())},
            reason="rejection_analysis_agent",
        )

        ctx.scratchpad["rejection_analysis"] = analysis

        await self._emit(
            ctx,
            msg,
            "rejection_analysis.completed",
            {"total_rejections": analysis["total_rejections"], "apps_updated": fixed},
        )

        return AgentResult(
            success=True,
            output={"analysis": analysis, "apps_updated": fixed},
            next_step_hint="reflection",
        )
