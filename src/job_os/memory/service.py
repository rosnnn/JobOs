from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.memory import MemoryRecord
from job_os.schemas.agents import MemoryWrite


class MemoryService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def write(self, data: MemoryWrite) -> MemoryRecord:
        stmt = select(MemoryRecord).where(MemoryRecord.memory_key == data.key)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.content = data.content
            existing.summary = data.summary
            existing.memory_type = data.memory_type
            existing.metadata_ = data.metadata
            await self._session.flush()
            return existing

        record = MemoryRecord(
            memory_key=data.key,
            memory_type=data.memory_type,
            content=data.content,
            summary=data.summary,
            metadata_=data.metadata,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def read(self, key: str) -> MemoryRecord | None:
        stmt = select(MemoryRecord).where(MemoryRecord.memory_key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def query_by_prefix(self, prefix: str, limit: int = 50) -> list[MemoryRecord]:
        stmt = (
            select(MemoryRecord)
            .where(MemoryRecord.memory_key.startswith(prefix))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
