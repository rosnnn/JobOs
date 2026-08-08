from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.api.deps import get_session
from job_os.memory.service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/query")
async def query_memory(
    prefix: str = Query(..., min_length=1),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    svc = MemoryService(session)
    records = await svc.query_by_prefix(prefix, limit=limit)
    return [
        {
            "key": r.memory_key,
            "type": r.memory_type,
            "content": r.content,
            "summary": r.summary,
        }
        for r in records
    ]
