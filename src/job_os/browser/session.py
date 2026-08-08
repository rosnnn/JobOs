"""Browser session lifecycle — Phase 3 implements full Playwright flows."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from job_os.config import get_settings
from job_os.models.browser import BrowserArtifact, BrowserSession


class BrowserSessionManager:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._settings = get_settings()

    async def create_session(self, *, job_url: str) -> BrowserSession:
        browser_session = BrowserSession(
            job_url=job_url,
            status="pending",
            started_at=datetime.now(timezone.utc),
        )
        self._session.add(browser_session)
        await self._session.flush()
        return browser_session

    async def save_artifact(
        self,
        browser_session_id: UUID,
        artifact_type: str,
        content: bytes,
        *,
        suffix: str = ".png",
    ) -> BrowserArtifact:
        settings = get_settings()
        artifact_dir = Path(settings.artifact_path) / str(browser_session_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{artifact_type}_{uuid4().hex[:8]}{suffix}"
        path = artifact_dir / filename
        path.write_bytes(content)

        artifact = BrowserArtifact(
            session_id=browser_session_id,
            artifact_type=artifact_type,
            file_path=str(path),
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

