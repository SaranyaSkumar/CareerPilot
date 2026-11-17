import re
import subprocess
import tempfile
import zipfile
from io import BytesIO

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


SAMPLE_EXPERIENCE = "\n".join(
    [
        "Software Engineer | 2022-2023",
        "Example Ltd | Auckland",
        "- Shipped a FastAPI service used by the billing team",
        "- Reduced p95 API latency from 400ms to 120ms",
        "",
        "Product Engineer | 2019-2021",
        "Northwind | Wellington",
        "- Rebuilt the customer portal in TypeScript",
    ]
)


def _pdftotext(pdf: bytes, raw: bool = False) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(pdf)
        handle.flush()
        command = ["pdftotext", "-enc", "UTF-8"]
        if raw:
            command.append("-raw")
        command.extend([handle.name, "-"])
        result = subprocess.run(command, check=True, capture_output=True)
    return result.stdout.decode("utf-8")


def _assert_order(text: str, snippets: list[str]) -> None:
    cursor = -1
    for snippet in snippets:
        index = text.find(snippet, cursor + 1)
        assert index != -1, f"missing {snippet!r} after position {cursor}\n{text}"
        cursor = index


def test_cv_export_reading_order_contact_line_and_docx_structure():
    profile = client.put(
        "/api/v1/profile",
        json={
            "full_name": "Alex Example",
            "email": "alex@example.com",
            "phone": "+64 21 555 0101",
            "location": "Auckland, New Zealand",
            "website_url": "https://alex.example",
            "linkedin_url": "https://www.linkedin.com/in/alex-example",
            "github_url": "https://github.com/alex-example",
        },
    )
    assert profile.status_code == 200
    saved = client.put(
        "/api/v1/cv",
        json={
            "name": "Alex Example",
            "headline": "Software Engineer",
            "summary": "Builds reliable services for New Zealand product teams.",
            "experience": SAMPLE_EXPERIENCE,
            "skills": "Python\nTypeScript\nPostgreSQL\nFastAPI",
            "education": "BSc Computer Science | University of Auckland | 2016-2019",
        },
    )
    assert saved.status_code == 200

    pdf = client.post("/api/v1/cv/export?format=pdf")
    assert pdf.status_code == 200
    assert b"/Subtype /Image" not in pdf.content
    assert b"/Subtype /Form" not in pdf.content
    raw = _pdftotext(pdf.content, raw=True)
    plain = _pdftotext(pdf.content, raw=False)
    expected = [
        "Alex Example",
        "Software Engineer",
        "alex@example.com",
        "+64 21 555 0101",
        "Auckland, New Zealand",
        "https://alex.example",
        "https://www.linkedin.com/in/alex-example",
        "https://github.com/alex-example",
        "PROFESSIONAL SUMMARY",
        "Builds reliable services",
        "EXPERIENCE",
        "Software Engineer",
        "2022-2023",
        "Example Ltd, Auckland",
        "Shipped a FastAPI service",
        "Product Engineer",
        "2019-2021",
        "Northwind, Wellington",
        "Rebuilt the customer portal",
        "SKILLS",
        "Python, TypeScript, PostgreSQL, FastAPI",
        "EDUCATION",
        "BSc Computer Science",
        "2016-2019",
        "University of Auckland",
    ]
    _assert_order(raw, expected)
    _assert_order(plain, expected[: expected.index("EDUCATION") + 1])
    assert "•" in raw
    assert not re.search(r"(?m)^\s*-\s+Shipped", raw)
    assert "LinkedIn" not in raw
    assert "GitHub" not in raw

    docx = client.post("/api/v1/cv/export?format=docx")
    assert docx.status_code == 200
    with zipfile.ZipFile(BytesIO(docx.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        styles_xml = archive.read("word/styles.xml").decode("utf-8")
        numbering_xml = archive.read("word/numbering.xml").decode("utf-8")
        names = archive.namelist()
    assert "Heading1" in document_xml
    assert "Title" in document_xml
    assert "ListBullet" in document_xml
    assert 'w:styleId="ListBullet"' in styles_xml
    assert "<w:numPr>" in styles_xml
    assert "w:num " in numbering_xml or "<w:num " in numbering_xml
    assert "w:drawing" not in document_xml
    assert "w:pict" not in document_xml
    assert "v:textbox" not in document_xml
    assert not any(name.startswith("word/header") or name.startswith("word/footer") for name in names)
    _assert_order(
        document_xml,
        [
            "Alex Example",
            "alex@example.com",
            "PROFESSIONAL SUMMARY",
            "EXPERIENCE",
            "Software Engineer",
            "2022-2023",
            "Example Ltd, Auckland",
            "Shipped a FastAPI service",
            "2019-2021",
            "SKILLS",
            "Python, TypeScript, PostgreSQL, FastAPI",
            "EDUCATION",
            "2016-2019",
        ],
    )


def test_cv_export_omits_blank_contact_fields_and_keeps_inline_role_dates():
    from app.cv_export import CvContact, build_pdf, format_contact_line, format_skill_lines

    assert format_contact_line(CvContact(email="a@b.c", github_url="https://github.com/a")) == (
        "a@b.c | https://github.com/a"
    )
    assert format_skill_lines("Languages: Python; SQL\nTools: Git, Docker\n- AWS") == [
        "Languages: Python, SQL",
        "Tools: Git, Docker",
        "AWS",
    ]

    saved = client.put(
        "/api/v1/profile",
        json={"email": "alex@example.com", "location": "", "phone": "", "website_url": "", "linkedin_url": "", "github_url": ""},
    )
    assert saved.status_code == 200
    assert client.put(
        "/api/v1/cv",
        json={
            "name": "Alex Example",
            "headline": "Software Engineer",
            "summary": "Builds APIs.",
            "experience": "Software Engineer | Example Ltd | 2022-present\nBuilt REST APIs with FastAPI.",
            "skills": "Python",
            "education": "BSc Computer Science",
        },
    ).status_code == 200
    pdf = client.post("/api/v1/cv/export?format=pdf")
    text = _pdftotext(pdf.content, raw=True)
    assert "alex@example.com" in text
    assert " | " not in text.split("PROFESSIONAL SUMMARY", 1)[0].split("alex@example.com", 1)[-1]
    _assert_order(
        text,
        ["Software Engineer", "2022-present", "Example Ltd", "Built REST APIs with FastAPI."],
    )
