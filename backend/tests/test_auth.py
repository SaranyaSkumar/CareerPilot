import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import reset_jwks_client
from app.database import Base, get_db
from app.main import app
from tests.api_client import AuthClient
from tests.jwt_support import (
    ISSUER,
    OTHER_PRIVATE_KEY,
    PRIVATE_KEY,
    USER_A,
    bearer,
    make_token,
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def auth_database():
    app.dependency_overrides[get_db] = override_get_db


client = AuthClient(app)
anonymous = TestClient(app)


def test_health_stays_public():
    response = anonymous.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_root_requires_a_verified_user():
    assert anonymous.get("/api/v1").status_code == 401
    authed = client.get("/api/v1")
    assert authed.status_code == 200
    assert authed.json()["version"] == "0.7.0"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/profile"),
        ("PUT", "/api/v1/profile"),
        ("GET", "/api/v1/cv"),
        ("PUT", "/api/v1/cv"),
        ("POST", "/api/v1/cv/export?format=pdf"),
        ("GET", "/api/v1/cv/versions"),
        ("POST", "/api/v1/cv/versions"),
        ("GET", "/api/v1/cv/versions/1"),
        ("POST", "/api/v1/cv/versions/1/restore"),
        ("POST", "/api/v1/cv/analyse"),
        ("GET", "/api/v1/cv/ai/status"),
        ("POST", "/api/v1/cv/ai/tailor"),
        ("POST", "/api/v1/cv/ai/improve-bullets"),
        ("POST", "/api/v1/cv/ai/adjust"),
        ("GET", "/api/v1/cv/variants"),
        ("POST", "/api/v1/cv/variants"),
        ("POST", "/api/v1/cv/variants/score"),
        ("POST", "/api/v1/cv/variants/clear-default"),
        ("PATCH", "/api/v1/cv/variants/1"),
        ("DELETE", "/api/v1/cv/variants/1"),
        ("POST", "/api/v1/cv/variants/1/duplicate"),
        ("POST", "/api/v1/cv/variants/1/default"),
        ("POST", "/api/v1/cv/variants/1/export?format=pdf"),
        ("POST", "/api/v1/cv/variants/1/analyse"),
        ("GET", "/api/v1/jobs"),
        ("POST", "/api/v1/jobs"),
        ("PATCH", "/api/v1/jobs/1"),
        ("DELETE", "/api/v1/jobs/1"),
        ("GET", "/api/v1/jobs/1/match"),
    ],
)
def test_missing_token_is_401(method, path):
    response = anonymous.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated."


def test_invalid_tokens_are_401():
    rejected = [
        "not-a-jwt",
        make_token(expires_in=-120),
        make_token(audience="anon"),
        make_token(issuer="https://evil.example/auth/v1"),
        make_token(role="service_role"),
        make_token(role=None),
        make_token(private_key=OTHER_PRIVATE_KEY, kid="other-key"),
        jwt.encode(
            {"sub": str(USER_A), "aud": "authenticated", "iss": ISSUER, "role": "authenticated"},
            "shared-secret",
            algorithm="HS256",
        ),
    ]
    for token in rejected:
        response = anonymous.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, token


def test_user_id_comes_from_the_token_not_the_request():
    claimed = str(uuid.uuid4())
    response = client.put(
        "/api/v1/profile",
        headers={"X-User-Id": claimed},
        json={
            "full_name": "Token Owner",
            "user_id": claimed,
            "email": "owner@example.com",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Token Owner"
    assert "user_id" not in body

    other = anonymous.get(
        "/api/v1/profile",
        headers={"Authorization": bearer(USER_A), "X-User-Id": claimed},
    )
    assert other.status_code == 200
    assert other.json()["full_name"] == ""


def test_startup_does_not_create_tables(monkeypatch):
    def refuse_create_all(*_args, **_kwargs):
        raise AssertionError("startup must not create tables")

    monkeypatch.setattr("app.database.Base.metadata.create_all", refuse_create_all)
    with TestClient(app) as probe:
        assert probe.get("/health").status_code == 200


def test_missing_supabase_url_fails_closed(monkeypatch):
    reset_jwks_client(None)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    response = anonymous.get("/api/v1/profile", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 503


def test_migration_sql_scopes_rows_and_keeps_rls():
    from pathlib import Path

    from migrations.sql_script import split_sql

    sql_path = Path(__file__).resolve().parents[1] / "migrations_sql" / "20261117_0001_add_user_scoping.sql"
    script = sql_path.read_text(encoding="utf-8")
    statements = split_sql(script)
    joined = "\n".join(statements)
    assert "DO $$" in joined
    assert joined.count("$$") % 2 == 0
    for table in ("career_profiles", "cv_documents", "cv_versions", "job_listings"):
        assert f"ENABLE ROW LEVEL SECURITY" in script
        assert f"{table}" in script
        assert "user_id uuid NOT NULL" in script
    assert "auth.uid()" in script
    assert "TO authenticated" in script
    assert "careerpilot_app" in script
    assert "REVOKE ALL ON TABLE" in script
    assert "FROM anon" in script
    assert "GRANT USAGE, SELECT ON SEQUENCE" in script
    migration = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions" / "20261117_0001_add_user_scoping.py"
    ).read_text(encoding="utf-8")
    assert "20261117_0001_add_user_scoping.sql" in migration
    assert "create_all" not in Path(__file__).resolve().parents[1].joinpath("app/main.py").read_text()


def test_contact_migration_adds_columns_without_dropping_rls():
    from pathlib import Path

    from migrations.sql_script import split_sql

    root = Path(__file__).resolve().parents[1]
    script = (root / "migrations_sql" / "20261117_0003_add_profile_contact_fields.sql").read_text(
        encoding="utf-8"
    )
    statements = split_sql(script)
    assert any("ADD COLUMN IF NOT EXISTS phone" in statement for statement in statements)
    for column in ("phone", "website_url", "linkedin_url", "github_url"):
        assert column in script
    assert "ENABLE ROW LEVEL SECURITY" in script
    assert "DISABLE ROW LEVEL SECURITY" not in script
    assert "DROP TABLE" not in script
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE career_profiles TO careerpilot_app" in script
    assert "FROM anon" in script
    migration = (
        root / "migrations" / "versions" / "20261117_0003_add_profile_contact_fields.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20261117_0002"' in migration
    assert "20261117_0003_add_profile_contact_fields.sql" in migration


def test_token_signed_with_the_test_key_is_accepted():
    token = jwt.encode(
        {
            "sub": str(USER_A),
            "aud": "authenticated",
            "iss": ISSUER,
            "role": "authenticated",
            "exp": int(__import__("time").time()) + 60,
        },
        PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": "test-signing-key"},
    )
    response = anonymous.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
