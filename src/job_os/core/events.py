from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.event import Event
from job_os.schemas.events import EventCreate


class EventService:
    """Append-only audit log for all agent and system actions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def emit(
        self,
        *,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
        workflow_id: UUID | None = None,
        step_id: str | None = None,
        agent_name: str | None = None,
        correlation_id: UUID | None = None,
        severity: str = "info",
    ) -> Event:
        event = Event(
            id=uuid4(),
            event_type=event_type,
            source=source,
            payload=payload or {},
            workflow_id=workflow_id,
            step_id=step_id,
            agent_name=agent_name,
            correlation_id=correlation_id or uuid4(),
            severity=severity,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def emit_from_schema(self, data: EventCreate) -> Event:
        return await self.emit(
            event_type=data.event_type,
            source=data.source,
            payload=data.payload,
            workflow_id=data.workflow_id,
            step_id=data.step_id,
            agent_name=data.agent_name,
            correlation_id=data.correlation_id,
            severity=data.severity,
        )
