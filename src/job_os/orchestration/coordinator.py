from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_os.agents.registry import AgentRegistry
from job_os.config import get_settings
from job_os.core.events import EventService
from job_os.memory.service import MemoryService
from job_os.models.workflow import Workflow, WorkflowStep
from job_os.orchestration.workflows import WORKFLOW_DEFINITIONS
from job_os.schemas.agents import AgentMessage, WorkflowContext
from job_os.world_model.service import WorldModelService


class Coordinator:
    """Workflow FSM executor — dispatches agents in sequence."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._events = EventService(session)
        self._registry = AgentRegistry(session, self._events)
        self._memory = MemoryService(session)

    async def start_workflow(
        self,
        workflow_type: str,
        *,
        mode: str | None = None,
        context: dict | None = None,
    ) -> Workflow:
        settings = get_settings()
        steps_def = WORKFLOW_DEFINITIONS.get(workflow_type)
        if not steps_def:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        correlation_id = uuid4()
        workflow = Workflow(
            workflow_type=workflow_type,
            status="running",
            mode=mode or settings.mode.value,
            context=context or {},
            correlation_id=correlation_id,
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(workflow)
        await self._session.flush()

        for order, step_def in enumerate(steps_def):
            step = WorkflowStep(
                workflow_id=workflow.id,
                step_id=step_def["step_id"],
                step_order=order,
                agent_name=step_def["agent_name"],
                status="pending",
                idempotency_key=f"{workflow.id}:{step_def['step_id']}",
                input_payload={"intent": step_def["intent"]},
            )
            self._session.add(step)

        await self._events.emit(
            event_type="workflow.started",
            source="coordinator",
            payload={"workflow_type": workflow_type},
            workflow_id=workflow.id,
            correlation_id=correlation_id,
        )
        await self._session.flush()
        return workflow

    async def run_workflow(self, workflow_id: UUID) -> Workflow:
        stmt = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        result = await self._session.execute(stmt)
        workflow = result.scalar_one()
        if workflow.status not in ("running", "pending", "awaiting_approval"):
            return workflow

        from job_os.services.profile_service import ProfileService

        world_svc = WorldModelService(self._session)
        world = await world_svc.get_current()
        user_profile = ProfileService().load()
        if user_profile:
            world = {**world, "user_profile": user_profile}

        from job_os.services.preferences_service import PreferencesService

        prefs = PreferencesService().load()
        if workflow.context:
            prefs = {**prefs, **workflow.context.get("job_preferences", {})}
        ctx = WorkflowContext(
            workflow_id=workflow.id,
            workflow_type=workflow.workflow_type,
            mode=workflow.mode,
            correlation_id=workflow.correlation_id,
            scratchpad={**dict(workflow.context), "job_preferences": prefs},
            world_state=world,
            user_profile=user_profile,
        )

        steps = sorted(workflow.steps, key=lambda s: s.step_order)
        for step in steps:
            if step.status == "completed":
                continue
            if workflow.status == "awaiting_approval":
                break

            agent = self._registry.get(step.agent_name)
            msg = AgentMessage(
                workflow_id=workflow.id,
                step_id=step.step_id,
                agent_name=step.agent_name,
                intent=step.input_payload.get("intent", "run"),
                payload=step.input_payload,
                correlation_id=workflow.correlation_id,
            )

            step.status = "running"
            step.started_at = datetime.now(timezone.utc)
            await self._session.flush()

            try:
                agent_result = await agent.run(ctx, msg)
            except Exception as exc:
                step.status = "failed"
                step.error_message = str(exc)
                workflow.status = "failed"
                workflow.error_message = str(exc)
                await self._events.emit(
                    event_type="workflow.step_failed",
                    source="coordinator",
                    payload={"step_id": step.step_id, "error": str(exc)},
                    workflow_id=workflow.id,
                    step_id=step.step_id,
                    correlation_id=workflow.correlation_id,
                    severity="error",
                )
                break

            step.output_payload = agent_result.output
            step.completed_at = datetime.now(timezone.utc)
            step.status = "completed" if agent_result.success else "failed"

            for mw in agent_result.memory_writes:
                await self._memory.write(mw)

            if agent_result.requires_approval:
                workflow.status = "awaiting_approval"
                await self._session.flush()
                return workflow

            if not agent_result.success:
                workflow.status = "failed"
                workflow.error_message = agent_result.error_detail
                break

        if workflow.status == "running":
            workflow.status = "completed"
            workflow.completed_at = datetime.now(timezone.utc)

        workflow.context = ctx.scratchpad
        await self._events.emit(
            event_type="workflow.completed",
            source="coordinator",
            payload={"status": workflow.status},
            workflow_id=workflow.id,
            correlation_id=workflow.correlation_id,
        )
        await self._session.flush()
        return workflow

    async def approve_and_resume(self, workflow_id: UUID) -> Workflow:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        result = await self._session.execute(stmt)
        workflow = result.scalar_one()
        if workflow.status != "awaiting_approval":
            return workflow
        workflow.status = "running"
        await self._session.flush()
        return await self.run_workflow(workflow_id)
