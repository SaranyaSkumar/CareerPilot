from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

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


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_cv_can_be_saved_and_retrieved():
    response = client.put(
        "/api/v1/cv",
        json={
            "name": "Alex Example",
            "headline": "Software Engineer",
            "summary": "Builds dependable applications.",
            "experience": "Software Engineer | Example Ltd | 2022–present",
            "skills": "Python, TypeScript",
            "education": "BSc Computer Science",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Alex Example"

    fetched = client.get("/api/v1/cv")
    assert fetched.status_code == 200
    assert fetched.json()["experience"].startswith("Software Engineer")


def test_cv_rejects_oversized_experience():
    response = client.put("/api/v1/cv", json={"experience": "x" * 15001})
    assert response.status_code == 422


def test_cv_can_be_exported_as_pdf_and_docx():
    saved = client.put(
        "/api/v1/cv",
        json={
            "name": "Alex Example",
            "headline": "Software Engineer",
            "summary": "Builds dependable applications.",
            "experience": "Software Engineer | Example Ltd | 2022-present",
            "skills": "Python, TypeScript",
            "education": "BSc Computer Science",
        },
    )
    assert saved.status_code == 200

    pdf = client.post("/api/v1/cv/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")

    docx = client.post("/api/v1/cv/export?format=docx")
    assert docx.status_code == 200
    assert "wordprocessingml.document" in docx.headers["content-type"]
    assert docx.content.startswith(b"PK")


def test_cv_export_rejects_unsupported_format():
    response = client.post("/api/v1/cv/export?format=html")
    assert response.status_code == 422


def test_cv_versions_are_immutable_snapshots_and_can_be_restored():
    original = {
        "name": "Alex Example",
        "headline": "Backend Engineer",
        "summary": "Builds reliable services.",
        "experience": "Backend Engineer | Example Ltd",
        "skills": "Python, FastAPI",
        "education": "BSc Computer Science",
    }
    saved = client.put("/api/v1/cv", json=original)
    assert saved.status_code == 200

    created = client.post(
        "/api/v1/cv/versions",
        json={"label": "Backend role", "job_title": "Backend Engineer", "company": "Example Ltd"},
    )
    assert created.status_code == 201
    version = created.json()
    assert version["snapshot"]["headline"] == "Backend Engineer"

    changed = {**original, "headline": "Platform Engineer", "skills": "Python, AWS"}
    assert client.put("/api/v1/cv", json=changed).status_code == 200

    history = client.get("/api/v1/cv/versions")
    assert history.status_code == 200
    matching = next(item for item in history.json() if item["id"] == version["id"])
    assert matching["snapshot"]["headline"] == "Backend Engineer"
    assert matching["snapshot"]["skills"] == "Python, FastAPI"

    restored = client.post(f"/api/v1/cv/versions/{version['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["headline"] == "Backend Engineer"


def test_cv_version_not_found_returns_404():
    response = client.post("/api/v1/cv/versions/999999/restore")
    assert response.status_code == 404


def test_cv_version_requires_saved_content():
    # Clear the singleton draft and verify empty drafts cannot be versioned.
    client.put("/api/v1/cv", json={})
    response = client.post("/api/v1/cv/versions", json={"label": "Empty"})
    assert response.status_code == 400
