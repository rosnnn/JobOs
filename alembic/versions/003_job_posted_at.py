"""Add posted_at for newest-first job ordering."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_posted_at", "jobs", ["posted_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_posted_at", table_name="jobs")
    op.drop_column("jobs", "posted_at")
