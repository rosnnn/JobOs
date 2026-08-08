from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memory_records"

    memory_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    memory_type: Mapped[str] = mapped_column(String(32), index=True)  # episodic, semantic, procedural
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
