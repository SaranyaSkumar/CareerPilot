import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CareerProfile, JobListing
from tests.api_client import AuthClient
from tests.jwt_support import DEFAULT_USER_ID

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


client = AuthClient(app)


@pytest.fixture(autouse=True)
def isolate_jobs_database():
    # Other test modules also override this app dependency at import time.
    # Re-apply this module's isolated session for every test.
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(JobListing).delete()
    db.query(CareerProfile).delete()
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



def test_job_match_endpoint_uses_saved_career_profile():
    db = TestingSessionLocal()
    db.add(CareerProfile(
        user_id=DEFAULT_USER_ID,
        headline="Software Engineer",
        location="Auckland, New Zealand",
        skills="Python, AWS, React",
    ))
    job = JobListing(
        user_id=DEFAULT_USER_ID,
        title="Software Engineer",
        company="Example",
        location="Auckland",
        description="Build APIs using Python and AWS. Docker experience is useful.",
        url="",
        source="Manual",
        status="saved",
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    response = client.get(f"/api/v1/jobs/{job_id}/match")

    assert response.status_code == 200
    result = response.json()
    assert "python" in result["matched_skills"]
    assert "aws" in result["matched_skills"]
    assert "docker" in result["not_found_skills"]
    assert result["score"] is not None
