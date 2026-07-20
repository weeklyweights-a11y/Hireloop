"""Add location_metro + indexes

Revision ID: 006
Revises: 005
Create Date: 2026-07-19
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN location_metro VARCHAR(100)")
    op.execute("CREATE INDEX idx_jobs_metro ON jobs(location_metro)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(location_country)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_metro")
    op.execute("DROP INDEX IF EXISTS idx_jobs_country")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS location_metro")
