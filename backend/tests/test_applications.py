import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CvVersion, JobApplication
from tests.api_client import AuthClient
from tests.jwt_support import DEFAULT_USER_ID

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
def isolate_applications_database():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.query(JobApplication).delete()
    db.query(CvVersion).delete()
    db.commit()
    db.close()


def test_application_lifecycle_and_stage_transition():
    created = client.post("/api/v1/applications", json={
        "title": "Software Engineer", "company": "Example", "location": "Auckland"
    })
    assert created.status_code == 201
    assert created.json()["stage"] == "interested"
    application_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"stage": "applied", "notes": "Submitted after review"},
    )
    assert updated.status_code == 200
    assert updated.json()["applied_at"] is not None
    assert updated.json()["notes"] == "Submitted after review"
    assert client.get("/api/v1/applications?stage=applied").json()[0]["id"] == application_id
    assert client.delete(f"/api/v1/applications/{application_id}").status_code == 204
    assert client.get("/api/v1/applications").json() == []


def test_application_rejects_blank_title_and_unknown_stage():
    assert client.post("/api/v1/applications", json={"title": " "}).status_code == 422
    created = client.post("/api/v1/applications", json={"title": "Backend Developer"})
    assert client.patch(
        f"/api/v1/applications/{created.json()['id']}", json={"stage": "magic"}
    ).status_code == 422


def test_application_can_attach_owned_cv_version_and_cover_letter():
    db = TestingSessionLocal()
    version = CvVersion(user_id=DEFAULT_USER_ID, label="Backend Engineer", snapshot={"name": "Test"})
    db.add(version)
    db.commit()
    version_id = version.id
    db.close()

    created = client.post("/api/v1/applications", json={"title": "Backend Engineer"})
    application_id = created.json()["id"]
    updated = client.patch(f"/api/v1/applications/{application_id}", json={
        "cv_version_id": version_id,
        "cover_letter": "  Dear hiring team,\\nI am interested.  ",
    })
    assert updated.status_code == 200
    assert updated.json()["cv_version_id"] == version_id
    assert updated.json()["cover_letter"] == "Dear hiring team,\\nI am interested."
    cleared = client.patch(f"/api/v1/applications/{application_id}", json={"cv_version_id": None})
    assert cleared.json()["cv_version_id"] is None


def test_application_cannot_attach_another_users_cv_version():
    db = TestingSessionLocal()
    other_user_id = DEFAULT_USER_ID.__class__("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    version = CvVersion(user_id=other_user_id, label="Private CV", snapshot={"name": "Other"})
    db.add(version)
    db.commit()
    version_id = version.id
    db.close()
    created = client.post("/api/v1/applications", json={"title": "Engineer"})
    response = client.patch(f"/api/v1/applications/{created.json()[\"id\"]}", json={"cv_version_id": version_id})
    assert response.status_code == 404


def test_user_cannot_read_or_modify_another_users_application():
    other_user_id = DEFAULT_USER_ID.__class__("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    db = TestingSessionLocal()
    item = JobApplication(user_id=other_user_id, title="Private role")
    db.add(item)
    db.commit()
    application_id = item.id
    db.close()

    assert client.get(f"/api/v1/applications?stage=interested").json() == []
    assert client.patch(
        f"/api/v1/applications/{application_id}", json={"notes": "intrusion"}
    ).status_code == 404
    assert client.delete(f"/api/v1/applications/{application_id}").status_code == 404
