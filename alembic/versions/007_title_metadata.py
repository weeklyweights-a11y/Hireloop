"""Add title_metadata JSONB

Revision ID: 007
Revises: 006
Create Date: 2026-07-19
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN title_metadata JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS title_metadata")
