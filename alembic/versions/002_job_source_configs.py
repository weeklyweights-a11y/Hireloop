"""job_source_configs table

Revision ID: 002
Revises: 001
Create Date: 2026-07-19
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE job_source_configs (
        id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        company_name            VARCHAR(255) NOT NULL,
        company_slug            VARCHAR(100) NOT NULL UNIQUE,
        company_logo_url        VARCHAR(500),
        company_website         VARCHAR(500),
        ats_type                VARCHAR(50) NOT NULL,
        api_endpoint            VARCHAR(1000) NOT NULL,
        api_method              VARCHAR(10) DEFAULT 'GET',
        api_headers             JSONB DEFAULT '{}',
        api_params              JSONB DEFAULT '{}',
        api_body                JSONB,
        response_path           VARCHAR(255),
        field_mapping           JSONB NOT NULL,
        pagination_config       JSONB DEFAULT '{}',
        polling_interval_hours  INTEGER DEFAULT 2,
        active                  BOOLEAN DEFAULT TRUE,
        last_polled_at          TIMESTAMPTZ,
        last_success_at         TIMESTAMPTZ,
        last_error              TEXT,
        total_jobs_found        INTEGER DEFAULT 0,
        created_at              TIMESTAMPTZ DEFAULT NOW(),
        updated_at              TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX idx_configs_active ON job_source_configs(active);
    CREATE INDEX idx_configs_ats ON job_source_configs(ats_type);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE job_source_configs;")
