import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import JobApplication

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
def isolate_applications_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(JobApplication).delete()
    db.commit()
    db.close()

def test_application_lifecycle_and_stage_transition():
    created = client.post("/api/v1/applications", json={"title": "Software Engineer", "company": "Example", "location": "Auckland"})
    assert created.status_code == 201
    assert created.json()["stage"] == "interested"
    application_id = created.json()["id"]
    updated = client.patch(f"/api/v1/applications/{application_id}", json={"stage": "applied", "notes": "Submitted after review"})
    assert updated.status_code == 200
    assert updated.json()["stage"] == "applied"
    assert updated.json()["applied_at"] is not None
    assert updated.json()["notes"] == "Submitted after review"
    assert client.get("/api/v1/applications?stage=applied").json()[0]["id"] == application_id
    assert client.delete(f"/api/v1/applications/{application_id}").status_code == 204
    assert client.get("/api/v1/applications").json() == []

def test_application_requires_title_and_rejects_unknown_stage():
    assert client.post("/api/v1/applications", json={"title": " "}).status_code == 422
    created = client.post("/api/v1/applications", json={"title": "Backend Developer"})
    assert client.patch(f"/api/v1/applications/{created.json()['id']}", json={"stage": "magic"}).status_code == 422

def test_missing_application_returns_404():
    assert client.patch("/api/v1/applications/12345", json={"notes": "x"}).status_code == 404
