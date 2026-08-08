from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workflow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflows"

    workflow_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    mode: Mapped[str] = mapped_column(String(32), default="supervised")
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps = relationship("WorkflowStep", back_populates="workflow", order_by="WorkflowStep.step_order")


class WorkflowStep(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_steps"

    workflow_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), index=True
    )
    step_id: Mapped[str] = mapped_column(String(64))
    step_order: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow = relationship("Workflow", back_populates="steps")
