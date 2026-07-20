"""jobs unique key: per-company instead of per-ATS

Revision ID: 005
Revises: 004
Create Date: 2026-07-19

A job's identity is (company, ats-assigned id). The original UNIQUE(source_ats,
source_job_id) collides across different companies on the same ATS — common for
"custom" tenants that reuse small numeric ids or share a backend host. Swap it
for UNIQUE(source_company_slug, source_job_id), which also matches how the differ
loads existing jobs.
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("jobs_source_ats_source_job_id_key", "jobs", type_="unique")
    op.create_unique_constraint(
        "jobs_source_company_slug_source_job_id_key",
        "jobs",
        ["source_company_slug", "source_job_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "jobs_source_company_slug_source_job_id_key", "jobs", type_="unique"
    )
    op.create_unique_constraint(
        "jobs_source_ats_source_job_id_key", "jobs", ["source_ats", "source_job_id"]
    )
