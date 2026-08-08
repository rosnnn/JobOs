from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    identity_id: UUID | None
    resume_id: UUID | None
    cover_letter_id: UUID | None
    status: str
    approval_status: str
    applied_at: datetime | None
    outcome: str | None
    outcome_at: datetime | None = None
    rejection_reason: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    job_title: str | None = None
    company_name: str | None = None
    job_url: str | None = None

    model_config = {"from_attributes": True}


class ResumeResponse(BaseModel):
    id: UUID
    identity_id: UUID
    version: int
    content_text: str | None
    content_path: str | None
    tailored_for_job_id: UUID | None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CoverLetterResponse(BaseModel):
    id: UUID
    job_id: UUID
    identity_id: UUID | None
    content_text: str
    version: int
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    step_id: str
    request_type: str
    payload: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
