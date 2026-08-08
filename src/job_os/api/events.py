from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.models.event import Event
from job_os.schemas.events import EventResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[EventResponse]:
    stmt = select(Event).order_by(Event.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    events = list(result.scalars().all())
    return [EventResponse.model_validate(e) for e in events]
