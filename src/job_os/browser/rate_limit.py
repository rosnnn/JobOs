"""Application rate limiting — prevents spam-like apply bursts."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_os.config import get_settings
from job_os.core.safety import SafetyValidator
from job_os.models.browser import RateLimitLedger


class RateLimitService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._settings = get_settings()
        self._safety = SafetyValidator()

    async def check_can_apply(self, *, source: str | None = None) -> tuple[bool, str | None]:
        today = date.today().isoformat()
        action_type = "application_submit"
        stmt = select(RateLimitLedger).where(
            RateLimitLedger.action_type == action_type,
            RateLimitLedger.action_date == today,
        )
        if source:
            stmt = stmt.where(RateLimitLedger.source == source)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        count = row.count if row else 0

        verdict = self._safety.check_application_rate(count, self._settings.max_applications_per_day)
        if not verdict.allowed:
            return False, verdict.violations[0]
        return True, None

    async def record_apply(self, *, source: str | None = None) -> None:
        today = date.today().isoformat()
        action_type = "application_submit"
        stmt = select(RateLimitLedger).where(
            RateLimitLedger.action_type == action_type,
            RateLimitLedger.action_date == today,
            RateLimitLedger.source == source,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.count += 1
        else:
            self._session.add(
                RateLimitLedger(
                    action_type=action_type,
                    source=source,
                    action_date=today,
                    count=1,
                )
            )
        await self._session.flush()
