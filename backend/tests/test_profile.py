from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from tests.api_client import AuthClient

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
client = AuthClient(app)


def test_profile_can_be_created_and_read():
    response = client.put(
        "/api/v1/profile",
        json={
            "full_name": "Alex Example",
            "email": "alex@example.com",
            "headline": "Software Engineer",
            "location": "Auckland, New Zealand",
            "summary": "Builds reliable software.",
            "skills": "Python, TypeScript",
        },
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Alex Example"

    fetched = client.get("/api/v1/profile")
    assert fetched.status_code == 200
    assert fetched.json()["skills"] == "Python, TypeScript"


def test_profile_rejects_oversized_summary():
    response = client.put("/api/v1/profile", json={"summary": "x" * 5001})
    assert response.status_code == 422
