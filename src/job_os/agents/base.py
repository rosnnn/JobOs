from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from job_os.core.events import EventService
from job_os.core.logging import get_logger
from job_os.schemas.agents import AgentMessage, AgentResult, WorkflowContext


class BaseAgent(ABC):
    """All specialist agents inherit this contract."""

    name: str = "base"
    version: str = "0.1.0"

    def __init__(self, session: AsyncSession, events: EventService):
        self._session = session
        self._events = events
        self._log = get_logger(f"agent.{self.name}")

    @abstractmethod
    async def run(self, ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
        ...

    async def _emit(
        self,
        ctx: WorkflowContext,
        msg: AgentMessage,
        event_type: str,
        payload: dict,
        severity: str = "info",
    ) -> None:
        await self._events.emit(
            event_type=event_type,
            source=self.name,
            payload=payload,
            workflow_id=ctx.workflow_id,
            step_id=msg.step_id,
            agent_name=self.name,
            correlation_id=ctx.correlation_id,
            severity=severity,
        )
