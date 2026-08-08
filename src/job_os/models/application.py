from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Application(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "applications"

    job_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), index=True)
    identity_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professional_identities.id"), nullable=True
    )
    resume_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True
    )
    cover_letter_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cover_letters.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    browser_session_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("browser_sessions.id"), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    job = relationship("Job", back_populates="applications")
    identity = relationship("ProfessionalIdentity", back_populates="applications")
    resume = relationship("Resume", back_populates="applications")
    cover_letter = relationship("CoverLetter", back_populates="applications")
    browser_session = relationship("BrowserSession", back_populates="application")
