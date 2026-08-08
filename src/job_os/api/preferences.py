from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from job_os.services.preferences_service import DEFAULT_PREFERENCES, PreferencesService

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesUpdate(BaseModel):
    remote_only: bool | None = None
    internship: bool | None = None
    full_time: bool | None = None
    sponsorship: bool | None = None
    fresher_friendly: bool | None = None
    recent_days: int | None = Field(None, ge=1, le=90)
    keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    experience_level: str | None = None
    locations: list[str] | None = None
    auto_apply_enabled: bool | None = None
    auto_apply_max_per_run: int | None = Field(None, ge=1, le=50)
    email_monitor_enabled: bool | None = None


@router.get("")
async def get_preferences() -> dict[str, Any]:
    return PreferencesService().load()


@router.put("")
async def update_preferences(body: PreferencesUpdate) -> dict[str, Any]:
    svc = PreferencesService()
    current = svc.load()
    updates = body.model_dump(exclude_none=True)
    return svc.save({**current, **updates})


@router.post("/reset")
async def reset_preferences() -> dict[str, Any]:
    return PreferencesService().save(dict(DEFAULT_PREFERENCES))
