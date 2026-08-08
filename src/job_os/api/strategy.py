from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.world_model.service import WorldModelService

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/world")
async def get_world_state(session: AsyncSession = Depends(get_session)) -> dict:
    svc = WorldModelService(session)
    return await svc.get_current()
