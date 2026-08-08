from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Recruiter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recruiters"

    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    responsiveness_score: Mapped[float | None] = mapped_column(nullable=True)
    interaction_history: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company = relationship("Company", back_populates="recruiters")
