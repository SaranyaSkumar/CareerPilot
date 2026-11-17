"""User A must not be able to read or change user B's career data."""

import io
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CareerProfile, CvDocument, CvVersion, JobListing
from tests.api_client import AuthClient
from tests.jwt_support import USER_A, USER_B

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

client_a = AuthClient(app, user_id=USER_A)
client_b = AuthClient(app, user_id=USER_B)

PROFILE_A = {
    "full_name": "User A Only",
    "email": "a@example.com",
    "headline": "Private headline A",
    "location": "Wellington",
    "summary": "Secret summary for A",
    "skills": "Hidden skill A",
}
CV_A = {
    "name": "ONLY-USER-A",
    "headline": "Staff Engineer",
    "summary": "Private CV summary for A",
    "experience": "ONLY-USER-A | Example Ltd | 2020-present",
    "skills": "Python",
    "education": "BSc",
}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolate_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(CvVersion).delete()
    db.query(JobListing).delete()
    db.query(CvDocument).delete()
    db.query(CareerProfile).delete()
    db.commit()
    db.close()


def test_profiles_are_private():
    saved = client_a.put("/api/v1/profile", json=PROFILE_A)
    assert saved.status_code == 200

    other = client_b.get("/api/v1/profile")
    assert other.status_code == 200
    assert other.json()["full_name"] == ""
    assert other.json()["summary"] == ""
    assert other.json()["id"] != saved.json()["id"]

    overwritten = client_b.put("/api/v1/profile", json={"full_name": "User B", "summary": "B only"})
    assert overwritten.status_code == 200
    assert client_a.get("/api/v1/profile").json()["full_name"] == "User A Only"
    assert client_a.get("/api/v1/profile").json()["summary"] == "Secret summary for A"


def test_cvs_versions_and_exports_are_private():
    saved = client_a.put("/api/v1/cv", json=CV_A)
    assert saved.status_code == 200
    cv_id = saved.json()["id"]
    created = client_a.post(
        "/api/v1/cv/versions",
        json={"label": "A snapshot", "job_title": "Staff Engineer", "company": "Secret Co"},
    )
    assert created.status_code == 201
    version_id = created.json()["id"]

    assert client_b.get("/api/v1/cv").json()["name"] == ""
    assert client_b.get("/api/v1/cv/versions").json() == []
    assert client_b.get(f"/api/v1/cv/versions/{version_id}").status_code == 404
    assert client_b.post(f"/api/v1/cv/versions/{version_id}/restore").status_code == 404
    assert client_b.get("/api/v1/cv").json()["name"] == ""
    assert client_a.get(f"/api/v1/cv/versions/{version_id}").json()["snapshot"]["name"] == "ONLY-USER-A"

    exported = client_a.post("/api/v1/cv/export?format=docx")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        document = archive.read("word/document.xml")
    assert b"ONLY-USER-A" in document
    pdf = client_a.post("/api/v1/cv/export?format=pdf")
    assert pdf.status_code == 200
    assert b"ONLY-USER-A" in pdf.content
    # Export has no document id. Guessing A's id, or exporting before B has content,
    # must not return A's file. B's first read created an empty draft, so the
    # export is refused instead of rendering A's CV.
    for path in (
        "/api/v1/cv/export?format=docx",
        "/api/v1/cv/export?format=pdf",
        f"/api/v1/cv/export?format=docx&id={cv_id}",
    ):
        hidden = client_b.post(path)
        assert hidden.status_code == 400
        assert b"ONLY-USER-A" not in hidden.content

    assert client_b.put(
        "/api/v1/cv",
        json={**CV_A, "name": "ONLY-USER-B", "experience": "ONLY-USER-B | Other Ltd | 2021-present"},
    ).status_code == 200
    b_pdf = client_b.post("/api/v1/cv/export?format=pdf")
    assert b_pdf.status_code == 200
    assert b"ONLY-USER-B" in b_pdf.content
    assert b"ONLY-USER-A" not in b_pdf.content
    a_pdf = client_a.post("/api/v1/cv/export?format=pdf")
    assert b"ONLY-USER-A" in a_pdf.content
    assert b"ONLY-USER-B" not in a_pdf.content

    guessed = client_b.post("/api/v1/cv/versions/999999/restore")
    assert guessed.status_code == 404


def test_jobs_are_private_including_guessed_ids():
    created = client_a.post(
        "/api/v1/jobs",
        json={
            "title": "A private role",
            "company": "Secret Employer",
            "url": "https://example.com/jobs/shared-url",
            "description": "Only A should see this description",
        },
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    assert client_b.get("/api/v1/jobs").json() == []
    assert client_b.get("/api/v1/jobs?q=Secret").json() == []
    assert client_b.patch(f"/api/v1/jobs/{job_id}", json={"status": "archived"}).status_code == 404
    assert client_b.delete(f"/api/v1/jobs/{job_id}").status_code == 404
    assert client_a.get("/api/v1/jobs").json()[0]["status"] == "saved"
    assert client_a.get("/api/v1/jobs").json()[0]["description"] == "Only A should see this description"

    duplicate_for_b = client_b.post(
        "/api/v1/jobs",
        json={"title": "B saved the same URL", "url": "https://example.com/jobs/shared-url"},
    )
    assert duplicate_for_b.status_code == 201
    assert client_b.patch(f"/api/v1/jobs/{job_id}", json={"status": "archived"}).status_code == 404
    assert client_b.patch("/api/v1/jobs/999999", json={"status": "archived"}).status_code == 404
    assert client_b.delete("/api/v1/jobs/999999").status_code == 404
