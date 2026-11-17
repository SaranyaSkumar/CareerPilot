"""Attach CV versions and cover letters to tracked applications.

Revision ID: 20261118_0007
Revises: 20261117_0006
Create Date: 2026-11-18
"""
from pathlib import Path

from alembic import op
from sqlalchemy import text

from migrations.sql_script import split_sql

revision = "20261118_0007"
down_revision = "20261117_0006"
branch_labels = None
depends_on = None

SQL_FILE = (
    Path(__file__).resolve().parents[2]
    / "migrations_sql"
    / "20261118_0007_application_documents.sql"
)


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS job_applications_cv_version_idx"))
    op.execute(text("ALTER TABLE job_applications DROP COLUMN IF EXISTS cover_letter"))
    op.execute(text("ALTER TABLE job_applications DROP COLUMN IF EXISTS cv_version_id"))
