"""Replace singleton career data with one owner per row.

Existing sample rows are deleted. The same change is stored as plain SQL in
backend/migrations_sql/20261117_0001_add_user_scoping.sql so it can be applied
in the Supabase SQL editor. Startup does not run this migration: the runtime
role cannot create tables.

Revision ID: 20261117_0001
Revises:
Create Date: 2026-11-17
"""

from pathlib import Path

from alembic import op
from sqlalchemy import text

from migrations.sql_script import split_sql

revision = "20261117_0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = (
    Path(__file__).resolve().parents[2]
    / "migrations_sql"
    / "20261117_0001_add_user_scoping.sql"
)


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    for table in ("job_listings", "cv_versions", "cv_documents", "career_profiles"):
        op.execute(text(f"DROP TABLE IF EXISTS {table}"))
