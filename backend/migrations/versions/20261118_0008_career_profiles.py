"""Add independent career profiles and attach tailored CV variants to them."""
from pathlib import Path
from alembic import op
from sqlalchemy import text
from migrations.sql_script import split_sql

revision = "20261118_0008"
down_revision = "20261118_0007"
branch_labels = None
depends_on = None
SQL_FILE = Path(__file__).resolve().parents[2] / "migrations_sql" / "20261118_0008_career_profiles.sql"


def upgrade() -> None:
    for statement in split_sql(SQL_FILE.read_text(encoding="utf-8")):
        op.execute(text(statement))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS cv_variants_profile_idx"))
    op.execute(text("ALTER TABLE cv_variants DROP COLUMN IF EXISTS profile_id"))
    op.execute(text("DROP TABLE IF EXISTS career_track_profiles"))
