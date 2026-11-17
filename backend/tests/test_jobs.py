import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import JobListing

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


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_jobs_database():
    # Other test modules also override this app dependency at import time.
    # Re-apply this module's isolated session for every test.
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(JobListing).delete()
    db.commit()
    db.close()


def test_job_can_be_saved_and_searched():
    created = client.post("/api/v1/jobs", json={
        "title": "Senior Software Engineer",
        "company": "Example NZ",
        "location": "Auckland, New Zealand",
        "description": "Python, TypeScript and AWS experience.",
        "url": "https://example.com/jobs/123",
        "source": "Company careers page",
    })
    assert created.status_code == 201
    assert created.json()["status"] == "saved"

    results = client.get("/api/v1/jobs?q=Python&location=Auckland&status=saved")
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["company"] == "Example NZ"


def test_duplicate_job_url_is_rejected():
    payload = {
        "title": "Backend Engineer",
        "url": "https://example.com/jobs/duplicate",
    }
    assert client.post("/api/v1/jobs", json=payload).status_code == 201
    duplicate = client.post("/api/v1/jobs", json=payload)
    assert duplicate.status_code == 409


def test_job_can_be_archived_and_restored():
    created = client.post("/api/v1/jobs", json={"title": "Platform Engineer"})
    job_id = created.json()["id"]

    archived = client.patch(f"/api/v1/jobs/{job_id}", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.get("/api/v1/jobs?status=saved").json() == []

    restored = client.patch(f"/api/v1/jobs/{job_id}", json={"status": "saved"})
    assert restored.status_code == 200
    assert restored.json()["status"] == "saved"


def test_missing_job_returns_404():
    response = client.patch("/api/v1/jobs/999999", json={"status": "archived"})
    assert response.status_code == 404


def test_job_title_is_required():
    response = client.post("/api/v1/jobs", json={"title": "   "})
    assert response.status_code == 422



def test_job_match_uses_saved_profile_and_cv_evidence():
    from app.models import CareerProfile, CvDocument

    client.put("/api/v1/profile", json={
        "headline": "Software Engineer",
        "location": "Auckland, New Zealand",
        "summary": "Backend developer building cloud applications.",
        "skills": "Python, TypeScript, AWS, PostgreSQL",
    })
    client.put("/api/v1/cv", json={
        "name": "Test Candidate",
        "headline": "Software Engineer",
        "summary": "Builds APIs and cloud applications.",
        "experience": "Developed Python services on AWS.",
        "skills": "Python, TypeScript, AWS, PostgreSQL",
        "education": "",
    })
    created = client.post("/api/v1/jobs", json={
        "title": "Software Engineer",
        "location": "Auckland, New Zealand",
        "description": "Required: Python, TypeScript, AWS and Docker experience.",
    })
    result = client.get(f"/api/v1/jobs/{created.json()['id']}/match")
    assert result.status_code == 200
    body = result.json()
    assert body["score"] > 0
    assert set(body["matched_skills"]) == {"python", "typescript", "aws"}
    assert "docker" in body["not_found_in_profile"]
    assert body["components"][0]["out_of"] == 70
    assert any("not proof" in item for item in body["limitations"])


def test_job_match_handles_missing_candidate_profile_and_job_description():
    created = client.post("/api/v1/jobs", json={"title": "Engineer"})
    result = client.get(f"/api/v1/jobs/{created.json()['id']}/match")
    assert result.status_code == 200
    body = result.json()
    assert body["score"] == 5
    assert body["matched_skills"] == []
    assert any("Add your verified skills" in item for item in body["limitations"])
