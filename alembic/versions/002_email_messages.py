"""Add email_messages table

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(512), nullable=False, unique=True),
        sa.Column("subject", sa.String(1024), server_default=""),
        sa.Column("from_address", sa.String(512), server_default=""),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classified_outcome", sa.String(64), nullable=True),
        sa.Column("company_name", sa.String(512), nullable=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_walk_in", sa.Boolean(), server_default="false"),
        sa.Column("is_interview", sa.Boolean(), server_default="false"),
        sa.Column("raw_headers", postgresql.JSONB(), server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_email_messages_classified_outcome", "email_messages", ["classified_outcome"])
    op.create_index("ix_email_messages_application_id", "email_messages", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_application_id", "email_messages")
    op.drop_index("ix_email_messages_classified_outcome", "email_messages")
    op.drop_table("email_messages")
