"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("domain", sa.String(256), nullable=True, unique=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("visa_sponsorship_history", postgresql.JSONB(), server_default="{}"),
        sa.Column("international_friendly_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_companies_name", "companies", ["name"])

    op.create_table(
        "professional_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role_focus", sa.String(128), nullable=False),
        sa.Column("ats_keywords", postgresql.JSONB(), server_default="[]"),
        sa.Column("project_emphasis", postgresql.JSONB(), server_default="[]"),
        sa.Column("tone", sa.String(64), server_default="professional"),
        sa.Column("base_resume_path", sa.String(512), nullable=True),
        sa.Column("performance_stats", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(512), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("company_name", sa.String(512), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("is_remote", sa.Boolean(), server_default="false"),
        sa.Column("offers_sponsorship", sa.Boolean(), nullable=True),
        sa.Column("fresher_friendly", sa.Boolean(), nullable=True),
        sa.Column("eligibility_score", sa.Float(), nullable=True),
        sa.Column("strategy_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), server_default="discovered"),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("parsed_metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reasons", postgresql.JSONB(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("mode", sa.String(32), server_default="supervised"),
        sa.Column("context", postgresql.JSONB(), server_default="{}"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "workflow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("step_id", sa.String(64), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("input_payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("output_payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), server_default="info"),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_id", sa.String(64), nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "memory_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("memory_key", sa.String(512), nullable=False, unique=True),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column("content", postgresql.JSONB(), server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("embedding_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "world_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("state", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "reflections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", sa.String(36), nullable=True),
        sa.Column("session_summary", sa.Text(), nullable=False),
        sa.Column("failures", postgresql.JSONB(), server_default="[]"),
        sa.Column("successes", postgresql.JSONB(), server_default="[]"),
        sa.Column("hypotheses", postgresql.JSONB(), server_default="[]"),
        sa.Column("recommended_actions", postgresql.JSONB(), server_default="[]"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "strategy_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("update_type", sa.String(64), nullable=False),
        sa.Column("target", sa.String(128), nullable=False),
        sa.Column("previous_value", postgresql.JSONB(), server_default="{}"),
        sa.Column("new_value", postgresql.JSONB(), server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("applied", sa.Boolean(), server_default="false"),
        sa.Column("reflection_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "market_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "recruiters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("linkedin_url", sa.String(512), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("responsiveness_score", sa.Float(), nullable=True),
        sa.Column("interaction_history", postgresql.JSONB(), server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professional_identities.id"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_path", sa.String(512), nullable=True),
        sa.Column("tailored_for_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "cover_letters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professional_identities.id"), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "browser_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professional_identities.id"), nullable=True),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=True),
        sa.Column("cover_letter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cover_letters.id"), nullable=True),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("approval_status", sa.String(32), server_default="pending"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("browser_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("browser_sessions.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "browser_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("browser_sessions.id"), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.String(64), nullable=False),
        sa.Column("request_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default="{}"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "rate_limit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("action_date", sa.String(10), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for table in [
        "rate_limit_ledger",
        "approval_requests",
        "browser_artifacts",
        "applications",
        "browser_sessions",
        "cover_letters",
        "resumes",
        "recruiters",
        "market_data",
        "strategy_updates",
        "reflections",
        "world_state",
        "memory_records",
        "events",
        "workflow_steps",
        "workflows",
        "jobs",
        "professional_identities",
        "companies",
    ]:
        op.drop_table(table)
