"""Add the user-scoped application tracker table.

Revision ID: 20261117_0006
Revises: 20261117_0005
Create Date: 2026-11-17
"""
from pathlib import Path

from alembic import op
from sqlalchemy import text

from migrations.sql_script import split_sql

revision = "20261117_0006"
down_revision = "20261117_0005"
branch_labels = None
depends_on = None

SQL_FILE = (
    Path(__file__).resolve().parents[2]
    / "migrations_sql"
    / "20261117_0006_application_tracker.sql"
)


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS job_applications"))
