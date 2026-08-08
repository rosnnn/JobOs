from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_os.models.workflow import Workflow
from job_os.orchestration.coordinator import Coordinator


class WorkflowService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._coordinator = Coordinator(session)

    async def create_and_run(self, workflow_type: str, *, mode: str | None = None, context: dict | None = None) -> Workflow:
        workflow = await self._coordinator.start_workflow(workflow_type, mode=mode, context=context)
        return await self._coordinator.run_workflow(workflow.id)

    async def get_workflow(self, workflow_id: UUID) -> Workflow | None:
        stmt = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def approve(self, workflow_id: UUID) -> Workflow:
        return await self._coordinator.approve_and_resume(workflow_id)

    async def run_submit_applications(self, *, mode: str | None = None) -> Workflow:
        return await self.create_and_run("submit_applications", mode=mode)
