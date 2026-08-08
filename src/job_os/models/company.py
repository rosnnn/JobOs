from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(512), index=True)
    domain: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    visa_sponsorship_history: Mapped[dict] = mapped_column(JSONB, default=dict)
    international_friendly_score: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    jobs = relationship("Job", back_populates="company")
    recruiters = relationship("Recruiter", back_populates="company")
