from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from job_os.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorldState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "world_state"

    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_current: Mapped[bool] = mapped_column(default=True, index=True)


class Reflection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reflections"

    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_summary: Mapped[str] = mapped_column(Text)
    failures: Mapped[list] = mapped_column(JSONB, default=list)
    successes: Mapped[list] = mapped_column(JSONB, default=list)
    hypotheses: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_actions: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class StrategyUpdate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "strategy_updates"

    update_type: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(128))
    previous_value: Mapped[dict] = mapped_column(JSONB, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    applied: Mapped[bool] = mapped_column(default=False)
    reflection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class MarketData(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "market_data"

    data_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
