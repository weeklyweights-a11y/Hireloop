"""jobs table

Revision ID: 001
Revises:
Create Date: 2026-07-19
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE jobs (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source_company_slug VARCHAR(100) NOT NULL,
        source_ats          VARCHAR(50) NOT NULL,
        source_job_id       VARCHAR(255) NOT NULL,
        source_url          VARCHAR(1000),
        apply_url           VARCHAR(1000),
        title_raw           VARCHAR(500) NOT NULL,
        title_normalized    VARCHAR(255),
        company_name        VARCHAR(255) NOT NULL,
        company_logo_url    VARCHAR(500),
        department          VARCHAR(255),
        location_city       VARCHAR(100),
        location_state      VARCHAR(50),
        location_country    VARCHAR(10) DEFAULT 'US',
        remote_policy       VARCHAR(20) DEFAULT 'unknown',
        seniority           VARCHAR(20),
        employment_type     VARCHAR(20) DEFAULT 'full_time',
        salary_min          INTEGER,
        salary_max          INTEGER,
        salary_currency     VARCHAR(10) DEFAULT 'USD',
        salary_period       VARCHAR(20) DEFAULT 'annual',
        experience_min      INTEGER,
        experience_max      INTEGER,
        skills_required     JSONB DEFAULT '[]',
        skills_nice_to_have JSONB DEFAULT '[]',
        visa_sponsorship    VARCHAR(20) DEFAULT 'unknown',
        description_text    TEXT,
        description_html    TEXT,
        status              VARCHAR(20) DEFAULT 'active',
        consecutive_misses  INTEGER DEFAULT 0,
        first_seen_at       TIMESTAMPTZ DEFAULT NOW(),
        last_verified_at    TIMESTAMPTZ DEFAULT NOW(),
        closed_at           TIMESTAMPTZ,
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(source_ats, source_job_id)
    );

    CREATE INDEX idx_jobs_status ON jobs(status);
    CREATE INDEX idx_jobs_source_status ON jobs(source_company_slug, status);
    CREATE INDEX idx_jobs_title_normalized ON jobs(title_normalized);
    CREATE INDEX idx_jobs_company ON jobs(company_name);
    CREATE INDEX idx_jobs_location ON jobs(location_city, location_state);
    CREATE INDEX idx_jobs_seniority ON jobs(seniority);
    CREATE INDEX idx_jobs_remote ON jobs(remote_policy);
    CREATE INDEX idx_jobs_employment ON jobs(employment_type);
    CREATE INDEX idx_jobs_salary ON jobs(salary_min, salary_max);
    CREATE INDEX idx_jobs_experience ON jobs(experience_min, experience_max);
    CREATE INDEX idx_jobs_visa ON jobs(visa_sponsorship);
    CREATE INDEX idx_jobs_first_seen ON jobs(first_seen_at);
    CREATE INDEX idx_jobs_last_verified ON jobs(last_verified_at);
    CREATE INDEX idx_jobs_skills_required ON jobs USING GIN (skills_required);
    CREATE INDEX idx_jobs_skills_nice ON jobs USING GIN (skills_nice_to_have);
    CREATE INDEX idx_jobs_description_fts ON jobs USING GIN (to_tsvector('english', description_text));
    """)


def downgrade() -> None:
    op.execute("DROP TABLE jobs;")
