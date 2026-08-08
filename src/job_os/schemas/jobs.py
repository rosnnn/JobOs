from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class JobIngest(BaseModel):
    external_id: str
    source: str
    title: str
    url: str
    company_name: str | None = None
    location: str | None = None
    raw_description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobEligibilityResult(BaseModel):
    job_id: UUID | None = None
    external_id: str
    eligible: bool
    eligibility_score: float = 0.0
    flags: dict[str, bool] = Field(default_factory=dict)
    reject_reasons: list[str] = Field(default_factory=list)


class JobRanked(BaseModel):
    job_id: UUID
    ev_score: float
    recommended_identity_slug: str | None = None
    rationale: str | None = None


class JobResponse(BaseModel):
    id: UUID
    external_id: str
    source: str
    title: str
    url: str
    company_name: str | None
    location: str | None
    is_remote: bool
    offers_sponsorship: bool | None
    fresher_friendly: bool | None
    eligibility_score: float | None
    strategy_score: float | None
    status: str
    reject_reasons: list[str]
    discovered_at: datetime | None
    posted_at: datetime | None = None
    match_score: float | None = None
    also_on: list[str] = Field(default_factory=list)
    board_label: str | None = None

    model_config = {"from_attributes": True}
