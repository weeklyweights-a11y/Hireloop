"""stats table

Revision ID: 004
Revises: 003
Create Date: 2026-07-19
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE stats (
        id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        total_active_jobs       INTEGER DEFAULT 0,
        total_companies         INTEGER DEFAULT 0,
        total_cities            INTEGER DEFAULT 0,
        jobs_added_last_24h     INTEGER DEFAULT 0,
        jobs_closed_last_24h    INTEGER DEFAULT 0,
        last_full_poll_at       TIMESTAMPTZ,
        avg_poll_duration_ms    INTEGER,
        updated_at              TIMESTAMPTZ DEFAULT NOW()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE stats;")
