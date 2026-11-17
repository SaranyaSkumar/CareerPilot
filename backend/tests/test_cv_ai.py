"""CV writing assistance: Anthropic is mocked; caps, auth, and grounding are real."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai_pricing import estimate_cost_usd, estimate_input_tokens
from app.database import Base, get_db
from app.main import app
from app.models import AiUsageEvent, CvDocument, JobListing
from app.cv_ai import ModelTailor
from tests.api_client import AuthClient
from tests.jwt_support import USER_A, USER_B

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

client = AuthClient(app, user_id=USER_A)
other = AuthClient(app, user_id=USER_B)
anonymous = TestClient(app)

CV = {
    "name": "Alex Example",
    "headline": "Software Engineer",
    "summary": "Builds dependable applications.",
    "experience": "Software Engineer | Example Ltd | 2022-present\n- Built the billing API in Python",
    "skills": "Python, TypeScript",
    "education": "BSc Computer Science",
}
CV_MARKER = "UNIQUE-CV-FACT-zebra"
JOB_MARKER = "UNIQUE-JOB-FACT-ember"


class FakeMessages:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        result = self.handler(kwargs)
        if isinstance(result, Exception):
            raise result
        parsed, input_tokens, output_tokens = result
        usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
        return SimpleNamespace(parsed_output=parsed, usage=usage)


class FakeAnthropic:
    def __init__(self, handler):
        self.messages = FakeMessages(handler)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def ai_database(monkeypatch):
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_DAILY_USER_CAP_USD", raising=False)
    monkeypatch.delenv("ANTHROPIC_MONTHLY_CAP_USD", raising=False)
    db = TestingSessionLocal()
    db.query(AiUsageEvent).delete()
    db.query(JobListing).delete()
    db.query(CvDocument).delete()
    db.commit()
    db.close()
    yield


def _validation_error() -> ValidationError:
    try:
        ModelTailor.model_validate({"summary": "Missing the support flag"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def _grounded_tailor() -> ModelTailor:
    return ModelTailor(
        summary="Builds dependable applications in Python.",
        summary_supported=True,
        summary_note="",
        bullets=[
            ModelBullet_line(0, "Software Engineer | Example Ltd | 2022-present"),
            ModelBullet_line(1, "Built the billing API in Python for dependable applications"),
        ],
        highlighted_skills=["Python", "Kubernetes"],
        could_not_support=["The job asks for Kubernetes, which is not in the CV."],
    )


def ModelBullet_line(source_line: int, text: str, supported: bool = True, support_note: str = ""):
    from app.cv_ai import ModelBullet

    return ModelBullet(
        source_line=source_line,
        text=text,
        supported=supported,
        support_note=support_note,
    )


def _save_cv(api: AuthClient = client, experience: str | None = None) -> dict:
    payload = dict(CV)
    if experience is not None:
        payload["experience"] = experience
    response = api.put("/api/v1/cv", json=payload)
    assert response.status_code == 200
    return response.json()


def _save_job(api: AuthClient = client, description: str = "Build APIs with Python.") -> dict:
    response = api.post(
        "/api/v1/jobs",
        json={
            "title": "Backend Engineer",
            "company": "Northwind",
            "location": "Wellington",
            "description": description,
        },
    )
    assert response.status_code == 201
    return response.json()


def _enable(monkeypatch, handler) -> FakeAnthropic:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake = FakeAnthropic(handler)
    monkeypatch.setattr("app.cv_ai.get_anthropic_client", lambda: fake)
    return fake


def _prompt_text(call: dict) -> str:
    return call["messages"][0]["content"]


def test_tailor_schema_rejects_a_draft_without_support_flags():
    with pytest.raises(ValidationError):
        ModelTailor.model_validate({"summary": "Builds dependable applications.", "bullets": []})


def test_tailor_schema_accepts_a_complete_draft():
    parsed = ModelTailor.model_validate(
        {
            "summary": "Builds dependable applications.",
            "summary_supported": True,
            "summary_note": "",
            "bullets": [
                {
                    "source_line": 1,
                    "text": "Built the billing API in Python",
                    "supported": True,
                    "support_note": "",
                }
            ],
            "highlighted_skills": ["Python"],
            "could_not_support": [],
        }
    )
    assert parsed.bullets[0].source_line == 1
    assert parsed.highlighted_skills == ["Python"]


def test_missing_key_returns_503_and_does_not_call_the_model(monkeypatch):
    called = False

    def explode():
        nonlocal called
        called = True
        raise AssertionError("the Anthropic client must not be constructed")

    monkeypatch.setattr("app.cv_ai.get_anthropic_client", explode)
    saved = _save_cv()
    job = _save_job()

    status = client.get("/api/v1/cv/ai/status")
    tailor = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    improve = client.post(
        "/api/v1/cv/ai/improve-bullets",
        json={"bullets": ["Built the billing API in Python"]},
    )
    for response in (status, tailor, improve):
        assert response.status_code == 503
        assert response.json()["detail"] == "AI not configured."
    assert called is False
    assert client.get("/api/v1/cv").json()["summary"] == saved["summary"]


def test_ai_routes_require_a_verified_user():
    assert anonymous.get("/api/v1/cv/ai/status").status_code == 401
    assert anonymous.post("/api/v1/cv/ai/tailor", json={"job_id": 1}).status_code == 401
    assert anonymous.post("/api/v1/cv/ai/improve-bullets", json={"bullets": ["x"]}).status_code == 401


def test_tailor_returns_a_grounded_suggestion_without_saving_it(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="careerpilot.ai")
    experience = f"Software Engineer | Example Ltd | 2022-present\n- Built the billing API in Python\n{CV_MARKER}"
    _save_cv(experience=experience)
    job = _save_job(description=f"Need Kubernetes. Mention {JOB_MARKER} and a 40% improvement.")
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 20000, 3000))

    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "tailor"
    assert body["job_title"] == "Backend Engineer"
    assert body["input_tokens"] == 20000
    assert body["output_tokens"] == 3000
    assert fake.messages.calls[0]["output_format"] is ModelTailor
    assert fake.messages.calls[0]["max_tokens"] <= 4096
    prompt = _prompt_text(fake.messages.calls[0])
    assert CV_MARKER in prompt
    assert JOB_MARKER in prompt
    assert "must not add" in fake.messages.calls[0]["system"]
    assert "UNTRUSTED JOB LISTING" in prompt

    summary = next(item for item in body["items"] if item["id"] == "summary")
    assert summary["unsupported"] is False
    assert summary["before"] == "Builds dependable applications."
    bullet = next(item for item in body["items"] if item["source_line"] == 1)
    assert bullet["unsupported"] is False
    assert bullet["before"].startswith("- Built the billing API")
    skill = next(item for item in body["items"] if item["section"] == "skills")
    assert skill["before"] == "Python"
    assert skill["unsupported"] is False
    assert any("Kubernetes" in note for note in body["could_not_support"])
    assert not any(item["after"] == "Kubernetes" and item["unsupported"] is False for item in body["items"])

    stored = client.get("/api/v1/cv").json()
    assert stored["summary"] == CV["summary"]
    assert CV_MARKER in stored["experience"]
    assert client.get("/api/v1/cv/versions").json() == []
    assert "input_tokens=20000" in caplog.text
    assert CV_MARKER not in caplog.text
    assert JOB_MARKER not in caplog.text
    status = client.get("/api/v1/cv/ai/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["model"] == "claude-sonnet-5-5"
    assert status.json()["daily_spent_usd"] == "0.07"
    assert status.json()["request_cap_usd"] == "0.50"


def test_job_only_metrics_are_flagged_and_not_treated_as_facts(monkeypatch):
    _save_cv()
    job = _save_job(description="Increased revenue by 40% at Stripe.")
    invented = ModelTailor(
        summary="Builds dependable applications.",
        summary_supported=True,
        bullets=[
            ModelBullet_line(0, "Software Engineer | Example Ltd | 2022-present"),
            ModelBullet_line(1, "Increased revenue by 40% after joining Stripe"),
        ],
        highlighted_skills=["Stripe"],
        could_not_support=[],
    )
    _enable(monkeypatch, lambda _kwargs: (invented, 100, 80))
    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 200
    bullet = next(item for item in response.json()["items"] if item["source_line"] == 1)
    assert bullet["unsupported"] is True
    assert "40%" in bullet["note"]
    assert "Stripe" in bullet["note"]
    assert any("Stripe" in note for note in response.json()["could_not_support"])
    assert "40%" not in client.get("/api/v1/cv").json()["experience"]


def test_schema_failure_is_502_and_does_not_count_against_the_cap(monkeypatch):
    _save_cv()
    job = _save_job()
    fake = _enable(monkeypatch, lambda _kwargs: _validation_error())
    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 502
    assert response.json()["detail"] == "The model did not return a usable suggestion."
    assert len(fake.messages.calls) == 2
    assert client.get("/api/v1/cv/ai/status").json()["daily_spent_usd"] == "0.00"
    db = TestingSessionLocal()
    rows = db.query(AiUsageEvent).all()
    db.close()
    assert len(rows) == 1
    assert rows[0].status == "released"


def test_request_over_fifty_cents_is_refused_before_the_model_is_called(monkeypatch):
    _save_cv()
    job = _save_job()
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 10, 10))
    monkeypatch.setattr("app.cv_ai.estimate_input_tokens", lambda *_parts: 400_000)
    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 429
    assert "US$0.50" in response.json()["detail"]
    assert fake.messages.calls == []
    db = TestingSessionLocal()
    assert db.query(AiUsageEvent).count() == 0
    db.close()


def test_daily_cap_blocks_the_next_call(monkeypatch):
    _save_cv()
    job = _save_job()
    db = TestingSessionLocal()
    db.add(
        AiUsageEvent(
            user_id=USER_A,
            operation="tailor",
            model="claude-sonnet-5-5",
            status="completed",
            input_tokens=10,
            output_tokens=10,
            estimated_cost_usd=Decimal("2.00"),
            actual_cost_usd=Decimal("2.00"),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 10, 10))
    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 429
    assert "daily AI limit" in response.json()["detail"]
    assert fake.messages.calls == []


def test_monthly_cap_is_app_wide(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MONTHLY_CAP_USD", "1")
    _save_cv()
    job = _save_job()
    db = TestingSessionLocal()
    db.add(
        AiUsageEvent(
            user_id=uuid.uuid4(),
            operation="tailor",
            model="claude-sonnet-5-5",
            status="completed",
            input_tokens=10,
            output_tokens=10,
            estimated_cost_usd=Decimal("1.00"),
            actual_cost_usd=Decimal("1.00"),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 10, 10))
    response = client.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 429
    assert "monthly AI limit" in response.json()["detail"]
    assert fake.messages.calls == []


def test_another_users_job_is_not_found_and_is_not_sent_to_the_model(monkeypatch):
    _save_cv(other)
    job = _save_job(client, description="Only the owner should be able to tailor against this.")
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 10, 10))
    response = other.post("/api/v1/cv/ai/tailor", json={"job_id": job["id"]})
    assert response.status_code == 404
    assert fake.messages.calls == []
    assert client.get("/api/v1/cv").json()["name"] == ""


def test_improve_rewrites_only_saved_lines_and_does_not_save(monkeypatch):
    _save_cv()
    from app.cv_ai import ModelImprove

    draft = ModelImprove(
        bullets=[
            ModelBullet_line(1, "Built the billing API in Python, keeping the service dependable"),
        ]
    )
    fake = _enable(monkeypatch, lambda _kwargs: (draft, 500, 120))
    response = client.post(
        "/api/v1/cv/ai/improve-bullets",
        json={"bullets": ["- Built the billing API in Python"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "improve_bullets"
    assert len(body["items"]) == 1
    assert body["items"][0]["unsupported"] is False
    assert body["items"][0]["before"] == "- Built the billing API in Python"
    assert "dependable" in body["items"][0]["after"]
    assert fake.messages.calls[0]["output_format"] is ModelImprove
    assert client.get("/api/v1/cv").json()["experience"] == CV["experience"]


def test_improve_rejects_lines_that_are_not_in_the_saved_cv(monkeypatch):
    _save_cv()
    fake = _enable(monkeypatch, lambda _kwargs: (_grounded_tailor(), 10, 10))
    response = client.post(
        "/api/v1/cv/ai/improve-bullets",
        json={"bullets": ["Increased revenue by 40% at a company I did not list"]},
    )
    assert response.status_code == 400
    assert "saved CV" in response.json()["detail"]
    assert fake.messages.calls == []


def test_maximum_saved_documents_stay_under_the_request_cap_even_with_one_retry():
    huge = "x" * (160 + 200 + 5000 + 15000 + 5000 + 8000 + 20000 + 8000)
    tokens = estimate_input_tokens(huge)
    cost = estimate_cost_usd("claude-sonnet-5-5", tokens, 4096) * 2
    assert cost <= Decimal("0.50")


def test_ai_usage_migration_enables_rls_and_does_not_drop_career_data():
    from pathlib import Path

    from migrations.sql_script import split_sql

    sql_path = Path(__file__).resolve().parents[1] / "migrations_sql" / "20261117_0002_add_ai_usage.sql"
    script = sql_path.read_text(encoding="utf-8")
    statements = split_sql(script)
    assert statements
    assert "DROP TABLE" not in script
    assert "ENABLE ROW LEVEL SECURITY" in script
    assert "ai_usage_events_owner" in script
    assert "(SELECT auth.uid()) = user_id" in script
    assert "TO authenticated" in script
    assert "careerpilot_app" in script
    assert "REVOKE ALL ON TABLE ai_usage_events FROM PUBLIC" in script
    assert "FROM anon" in script
    assert "GRANT USAGE, SELECT ON SEQUENCE ai_usage_events_id_seq" in script
    assert script.count("$$") % 2 == 0
    migration = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions" / "20261117_0002_add_ai_usage.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20261117_0001"' in migration
    assert "20261117_0002_add_ai_usage.sql" in migration
