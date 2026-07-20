"""poll_logs table

Revision ID: 003
Revises: 002
Create Date: 2026-07-19
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE poll_logs (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_config_id    UUID REFERENCES job_source_configs(id),
        company_name        VARCHAR(255),
        status              VARCHAR(20) NOT NULL,
        jobs_found          INTEGER DEFAULT 0,
        jobs_new            INTEGER DEFAULT 0,
        jobs_updated        INTEGER DEFAULT 0,
        jobs_closed         INTEGER DEFAULT 0,
        duration_ms         INTEGER,
        error_message       TEXT,
        polled_at           TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX idx_poll_logs_source ON poll_logs(source_config_id);
    CREATE INDEX idx_poll_logs_polled ON poll_logs(polled_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE poll_logs;")
