"""Add per-user job discovery settings and provider cache tables.

The same change is stored as plain SQL in
backend/migrations_sql/20261117_0003_job_discovery.sql so it can be applied in
the Supabase SQL editor. Startup does not run this migration: the runtime role
cannot create tables.

Revision ID: 20261117_0003
Revises: 20261117_0002
Create Date: 2026-11-17
"""

from pathlib import Path

from alembic import op
from sqlalchemy import text

from migrations.sql_script import split_sql

revision = "20261117_0003"
down_revision = "20261117_0002"
branch_labels = None
depends_on = None

SQL_FILE = (
    Path(__file__).resolve().parents[2] / "migrations_sql" / "20261117_0003_job_discovery.sql"
)


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS job_provider_quota"))
    op.execute(text("DROP TABLE IF EXISTS job_provider_cache"))
    op.execute(text("DROP TABLE IF EXISTS job_provider_settings"))
    op.execute(text("DROP TABLE IF EXISTS job_discovery_settings"))
    op.execute(text("DROP INDEX IF EXISTS job_listings_user_dedupe_unique"))
    op.execute(text("ALTER TABLE job_listings DROP COLUMN IF EXISTS dedupe_key"))
    op.execute(text("ALTER TABLE job_listings DROP COLUMN IF EXISTS posted_at"))
    op.execute(text("ALTER TABLE job_listings DROP COLUMN IF EXISTS salary"))
