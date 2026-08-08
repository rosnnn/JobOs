from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    workflow_type: str = "daily_discovery"
    mode: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResponse(BaseModel):
    id: UUID
    step_id: str
    step_order: int
    agent_name: str
    status: str
    output_payload: dict[str, Any]

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: UUID
    workflow_type: str
    status: str
    mode: str
    correlation_id: UUID
    context: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    steps: list[WorkflowStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    approved: bool
    notes: str | None = None
    decided_by: str = "operator"
