from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )

    external_id: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text)
    company_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    company_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_remote: Mapped[bool] = mapped_column(default=False)
    offers_sponsorship: Mapped[bool | None] = mapped_column(nullable=True)
    fresher_friendly: Mapped[bool | None] = mapped_column(nullable=True)
    eligibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="discovered", index=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reject_reasons: Mapped[list] = mapped_column(JSONB, default=list)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job")
