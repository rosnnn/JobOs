from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_messages"

    message_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(1024), default="")
    from_address: Mapped[str] = mapped_column(String(512), default="")
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    classified_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    application_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_walk_in: Mapped[bool] = mapped_column(default=False)
    is_interview: Mapped[bool] = mapped_column(default=False)
    raw_headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
