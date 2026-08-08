from job_os.agents.base import BaseAgent
from job_os.models.intelligence import Reflection, StrategyUpdate
from job_os.schemas.agents import AgentMessage, AgentResult, MemoryWrite, WorkflowContext
from job_os.world_model.service import WorldModelService


class ReflectionAgent(BaseAgent):
    name = "reflection"
    version = "0.2.0"

    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        metrics = ctx.scratchpad.get("session_metrics", {})
        ranked = ctx.scratchpad.get("ranked_jobs", [])
        applications = ctx.scratchpad.get("applications", [])

        failures: list[str] = []
        successes: list[str] = []
        hypotheses: list[str] = []
        actions: list[str] = []

        if metrics.get("qualified", 0) == 0:
            failures.append("zero_qualified_jobs")
            actions.append("expand_sources_or_relax_soft_filters")
        else:
            successes.append(f"qualified_{metrics['qualified']}_jobs")

        if metrics.get("applications_draft", 0) > 0:
            successes.append(f"prepared_{metrics['applications_draft']}_applications")
        elif metrics.get("ranked", 0) > 0:
            failures.append("no_applications_prepared")
            actions.append("check_resume_tailoring_errors")

        if ranked:
            top = ranked[0]
            hypotheses.append(
                f"top_opportunity_ev={top.get('ev_score')}_identity={top.get('recommended_identity_slug')}"
            )

        summary = (
            f"Session {ctx.workflow_id}: discovered={metrics.get('discovered', 0)}, "
            f"qualified={metrics.get('qualified', 0)}, ranked={metrics.get('ranked', 0)}, "
            f"applications={metrics.get('applications_draft', 0)}"
        )

        reflection = Reflection(
            workflow_id=str(ctx.workflow_id),
            session_summary=summary,
            failures=failures,
            successes=successes,
            hypotheses=hypotheses,
            recommended_actions=actions,
            metadata_={"metrics": metrics},
        )
        self._session.add(reflection)
        await self._session.flush()

        strategy_updates = await self._emit_strategy_updates(ctx, reflection, metrics, ranked)
        await self._update_world_model(metrics, ranked)

        await self._emit(
            ctx,
            msg,
            "reflection.completed",
            {
                "reflection_id": str(reflection.id),
                "summary": summary,
                "strategy_updates": len(strategy_updates),
            },
        )

        return AgentResult(
            success=True,
            output={
                "reflection_id": str(reflection.id),
                "summary": summary,
                "strategy_update_ids": strategy_updates,
            },
            memory_writes=[
                MemoryWrite(
                    key=f"workflow:{ctx.workflow_id}:reflection",
                    memory_type="episodic",
                    content={
                        "failures": failures,
                        "successes": successes,
                        "hypotheses": hypotheses,
                        "applications": len(applications),
                    },
                    summary=summary,
                )
            ],
        )

    async def _emit_strategy_updates(
        self,
        ctx: WorkflowContext,
        reflection: Reflection,
        metrics: dict,
        ranked: list,
    ) -> list[str]:
        updates: list[str] = []

        if metrics.get("discovered", 0) > 0:
            yield_rate = metrics.get("qualified", 0) / max(metrics.get("discovered", 1), 1)
            update = StrategyUpdate(
                update_type="source_yield_estimate",
                target="global",
                previous_value=ctx.world_state.get("source_yield", {}),
                new_value={"session_yield": round(yield_rate, 3), "discovered": metrics["discovered"]},
                reason="Session qualification rate observed",
                confidence=0.6,
                applied=False,
                reflection_id=str(reflection.id),
            )
            self._session.add(update)
            await self._session.flush()
            updates.append(str(update.id))

        if ranked and metrics.get("applications_draft", 0) > 0:
            top = ranked[0]
            slug = top.get("recommended_identity_slug")
            if slug:
                update = StrategyUpdate(
                    update_type="identity_performance_hint",
                    target=slug,
                    previous_value={},
                    new_value={"last_top_rank": True, "ev_score": top.get("ev_score")},
                    reason="Identity selected for top-ranked job in session",
                    confidence=0.5,
                    applied=False,
                    reflection_id=str(reflection.id),
                )
                self._session.add(update)
                await self._session.flush()
                updates.append(str(update.id))

        return updates

    async def _update_world_model(self, metrics: dict, ranked: list) -> None:
        world_svc = WorldModelService(self._session)
        patch: dict = {
            "market_conditions": {
                "last_session_discovered": metrics.get("discovered", 0),
                "last_session_qualified": metrics.get("qualified", 0),
            },
        }
        if ranked:
            patch["resume_performance"] = {
                ranked[0].get("recommended_identity_slug", "unknown"): {
                    "last_ev_score": ranked[0].get("ev_score"),
                }
            }
        await world_svc.merge_update(patch, reason="reflection_session")
