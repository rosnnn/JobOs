from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.models.intelligence import WorldState
from job_os.world_model.defaults import DEFAULT_WORLD_STATE


class WorldModelService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_current(self) -> dict:
        stmt = select(WorldState).where(WorldState.is_current.is_(True)).order_by(WorldState.version.desc())
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return row.state
        return await self._bootstrap()

    async def _bootstrap(self) -> dict:
        row = WorldState(version=1, state=DEFAULT_WORLD_STATE.copy(), is_current=True)
        self._session.add(row)
        await self._session.flush()
        return row.state

    async def merge_update(self, partial: dict, *, reason: str = "") -> dict:
        current = await self.get_current()

        # Mark old version inactive
        stmt = select(WorldState).where(WorldState.is_current.is_(True))
        result = await self._session.execute(stmt)
        old = result.scalar_one_or_none()
        if old:
            old.is_current = False

        merged = _deep_merge(current, partial)
        new_row = WorldState(
            version=(old.version + 1) if old else 1,
            state=merged,
            is_current=True,
        )
        self._session.add(new_row)
        await self._session.flush()
        return merged


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
