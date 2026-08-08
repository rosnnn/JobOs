from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    event_type: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    workflow_id: UUID | None = None
    step_id: str | None = None
    agent_name: str | None = None
    correlation_id: UUID | None = None
    severity: str = "info"


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    source: str
    severity: str
    workflow_id: UUID | None
    step_id: str | None
    agent_name: str | None
    correlation_id: UUID
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
