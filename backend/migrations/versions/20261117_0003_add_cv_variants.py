"""Add named CV variants that sit beside the original draft.

The same change is stored as plain SQL in
backend/migrations_sql/20261117_0003_add_cv_variants.sql so it can be applied
in the Supabase SQL editor. Startup does not run this migration: the runtime
role cannot create tables.

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
    Path(__file__).resolve().parents[2] / "migrations_sql" / "20261117_0003_add_cv_variants.sql"
)


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS cv_variants"))
