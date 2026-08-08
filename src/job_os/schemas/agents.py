from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    workflow_id: UUID
    step_id: str
    agent_name: str
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID


class MemoryWrite(BaseModel):
    key: str
    memory_type: str
    content: dict[str, Any]
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    memory_writes: list[MemoryWrite] = Field(default_factory=list)
    next_step_hint: str | None = None
    requires_approval: bool = False
    error_code: str | None = None
    error_detail: str | None = None


class WorkflowContext(BaseModel):
    workflow_id: UUID
    workflow_type: str
    mode: str
    correlation_id: UUID
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    world_state: dict[str, Any] = Field(default_factory=dict)
    user_profile: dict[str, Any] = Field(default_factory=dict)
