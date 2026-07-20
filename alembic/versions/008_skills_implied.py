"""Add skills_implied JSONB + GIN indexes

Revision ID: 008
Revises: 007
Create Date: 2026-07-19
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN skills_implied JSONB DEFAULT '[]'")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_skills_required_gin "
        "ON jobs USING GIN (skills_required)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_skills_implied_gin "
        "ON jobs USING GIN (skills_implied)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_skills_implied_gin")
    op.execute("DROP INDEX IF EXISTS idx_jobs_skills_required_gin")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS skills_implied")
