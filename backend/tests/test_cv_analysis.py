from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from tests.api_client import AuthClient

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = AuthClient(app)

def save_cv(**overrides):
    payload = {
        "name": "Alex Example",
        "headline": "Software Engineer",
        "summary": "Builds reliable Python services.",
        "experience": "Software Engineer | Example Ltd | 2022-present\nBuilt REST APIs with FastAPI.",
        "skills": "Python, FastAPI, PostgreSQL",
        "education": "BSc Computer Science",
    }
    payload.update(overrides)
    return client.put("/api/v1/cv", json=payload)

def test_general_analysis_returns_formatting_checks_without_job_score():
    assert save_cv().status_code == 200
    response = client.post("/api/v1/cv/analyse", json={})
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["formatting_score"] <= 100
    assert body["content_score"] is None
    assert body["overall_score"] is None
    assert any(item["code"] == "layout_limit" for item in body["findings"])

def test_job_analysis_reports_keyword_coverage():
    assert save_cv().status_code == 200
    response = client.post("/api/v1/cv/analyse", json={
        "job_description": "We need a Python and FastAPI engineer with AWS, Docker and PostgreSQL experience."
    })
    assert response.status_code == 200
    body = response.json()
    assert body["content_score"] is not None
    assert body["overall_score"] is not None
    statuses = {item["term"]: item["status"] for item in body["keywords"]}
    assert statuses["python"] == "matched"
    assert statuses["fastapi"] == "matched"
    assert statuses["aws"] == "missing"
    assert "does not prove" in next(item["evidence"] for item in body["keywords"] if item["term"] == "aws")

def test_analysis_handles_empty_cv_without_inventing_content():
    client.put("/api/v1/cv", json={})
    response = client.post("/api/v1/cv/analyse", json={"job_description": "Python AWS Docker"})
    assert response.status_code == 200
    body = response.json()
    assert body["formatting_score"] < 100
    assert all(item["status"] == "missing" for item in body["keywords"])
    assert any(item["code"] == "missing_experience" for item in body["findings"])

def test_analysis_rejects_oversized_job_description():
    response = client.post("/api/v1/cv/analyse", json={"job_description": "x" * 20001})
    assert response.status_code == 422
