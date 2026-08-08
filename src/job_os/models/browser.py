from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BrowserSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_sessions"

    job_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    artifacts = relationship("BrowserArtifact", back_populates="session")
    application = relationship("Application", back_populates="browser_session", uselist=False)


class BrowserArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "browser_artifacts"

    session_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("browser_sessions.id"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32))  # screenshot, html, log
    file_path: Mapped[str] = mapped_column(String(1024))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    session = relationship("BrowserSession", back_populates="artifacts")


class ApprovalRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approval_requests"

    workflow_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True)
    step_id: Mapped[str] = mapped_column(String(64))
    request_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RateLimitLedger(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rate_limit_ledger"

    action_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    count: Mapped[int] = mapped_column(default=0)
