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
