"""Discovery settings, mocked provider calls, dedupe, and per-user isolation."""

import ipaddress

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.job_providers.http import set_http_client
from app.job_providers.page_fetch import set_resolver
from app.main import app
from app.models import (
    CareerProfile,
    JobDiscoverySettings,
    JobListing,
    JobProviderCache,
    JobProviderQuota,
    JobProviderSetting,
)
from tests.api_client import AuthClient
from tests.jwt_support import DEFAULT_USER_ID, USER_A, USER_B

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

client = AuthClient(app)
client_a = AuthClient(app, user_id=USER_A)
client_b = AuthClient(app, user_id=USER_B)
calls: list[httpx.Request] = []

ADZUNA = {
    "results": [
        {
            "title": "Software Engineer",
            "redirect_url": "https://example.com/jobs/engineer",
            "company": {"display_name": "Example NZ"},
            "location": {"display_name": "Auckland"},
            "description": "Build APIs with Python and AWS.",
            "created": "2026-11-01T00:00:00Z",
            "salary_min": 90000,
            "salary_max": 120000,
            "salary_is_predicted": 0,
        },
        {
            "title": "Nurse",
            "redirect_url": "https://example.com/jobs/nurse",
            "company": {"display_name": "Care Co"},
            "location": {"display_name": "Wellington"},
            "description": "Ward nursing.",
            "created": "2026-11-02T00:00:00Z",
        },
    ]
}
JOOBLE = {
    "totalCount": 3,
    "jobs": [
        {
            "title": "software engineer",
            "link": "https://jooble.example/engineer",
            "company": "Example NZ",
            "location": "Auckland",
            "snippet": "Python role",
            "salary": "90000 NZD",
            "updated": "2026-11-01T00:00:00.0000000",
            "id": 1,
        },
        {
            "title": "Analyst",
            "link": "https://example.com/jobs/nurse/",
            "company": "Other",
            "location": "Wellington",
            "snippet": "Data",
            "id": 2,
        },
        {
            "title": "Designer",
            "link": "https://example.com/jobs/designer?utm_source=jooble",
            "company": "Studio",
            "location": "Dunedin",
            "snippet": "<b>Design</b> systems",
            "id": 3,
        },
    ],
}
JOB_PAGE = """
<html><head>
<script type="application/ld+json">
{"@type":"JobPosting","title":"Platform Engineer","description":"<p>Build Python services.</p>",
 "hiringOrganization":{"name":"Harbour Labs"},
 "jobLocation":{"address":{"addressLocality":"Auckland","addressCountry":"NZ"}},
 "datePosted":"2026-11-10",
 "baseSalary":{"currency":"NZD","value":{"minValue":100000,"maxValue":130000,"unitText":"YEAR"}}}
</script>
</head></html>
"""


def handler(request: httpx.Request) -> httpx.Response:
    calls.append(request)
    url = str(request.url)
    if "api.adzuna.com" in url:
        return httpx.Response(200, json=ADZUNA)
    if "jooble.org" in url:
        return httpx.Response(200, json=JOOBLE)
    if request.url.host == "jobs.example" and request.url.path == "/go":
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
    if request.url.host == "jobs.example":
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=JOB_PAGE)
    raise AssertionError(f"unexpected request {request.method} {request.url.host}{request.url.path}")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "test-app")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-key")
    monkeypatch.setenv("JOOBLE_API_KEY", "testjooblekey")
    monkeypatch.setenv("JOOBLE_API_BASE", "https://jooble.org/api")
    monkeypatch.setenv("JOB_DISCOVERY_INTERACTIVE_SECONDS", "0")
    monkeypatch.setenv("JOB_DISCOVERY_DAILY_SECONDS", "0")
    monkeypatch.setenv("JOB_DISCOVERY_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("JOB_DISCOVERY_CACHE_SECONDS", "43200")
    monkeypatch.delenv("ADZUNA_DAILY_LIMIT", raising=False)
    monkeypatch.delenv("JOOBLE_DAILY_LIMIT", raising=False)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    for model in (
        JobListing,
        JobProviderSetting,
        JobDiscoverySettings,
        JobProviderCache,
        JobProviderQuota,
        CareerProfile,
    ):
        db.query(model).delete()
    db.commit()
    db.close()
    calls.clear()
    set_http_client(httpx.Client(transport=httpx.MockTransport(handler)))
    set_resolver(lambda _host: [ipaddress.ip_address("93.184.216.34")])
    yield
    set_http_client(None)
    set_resolver(None)


def test_discovery_dedupes_providers_and_reuses_the_cache():
    first = client.post("/api/v1/jobs/discovery")
    assert first.status_code == 200
    body = first.json()
    assert body["created"] == 3
    assert body["cached"] is False
    assert {item["provider_key"] for item in body["providers"]} == {"adzuna", "jooble"}
    assert len(calls) == 2
    adzuna = next(call for call in calls if "api.adzuna.com" in str(call.url))
    assert "/jobs/nz/search/1" in adzuna.url.path
    assert adzuna.url.params["content-type"] == "application/json"
    assert adzuna.url.params["app_id"] == "test-app"
    jooble = next(call for call in calls if "jooble.org" in str(call.url))
    assert jooble.method == "POST"
    assert jooble.read().decode().count("testjooblekey") == 0

    listed = client.get("/api/v1/jobs?status=discovered&sort=match")
    assert listed.status_code == 200
    titles = {job["title"] for job in listed.json()}
    assert titles == {"Software Engineer", "Nurse", "Designer"}
    engineer = next(job for job in listed.json() if job["title"] == "Software Engineer")
    assert engineer["source"] == "Adzuna"
    assert engineer["salary"] == "NZD 90,000–120,000"
    assert engineer["company"] == "Example NZ"
    designer = next(job for job in listed.json() if job["title"] == "Designer")
    assert designer["source"] == "Jooble"
    assert designer["url"] == "https://example.com/jobs/designer"
    assert "Design" in designer["description"]
    assert "<b>" not in designer["description"]

    second = client.post("/api/v1/jobs/discovery")
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert len(calls) == 2
    assert client.get("/api/v1/jobs?status=discovered").json().__len__() == 3


def test_shared_cache_does_not_copy_one_users_jobs_to_another():
    assert client_a.post("/api/v1/jobs/discovery").status_code == 200
    assert len(calls) == 2
    other = client_b.post("/api/v1/jobs/discovery")
    assert other.status_code == 200
    assert other.json()["created"] == 3
    assert len(calls) == 2

    own = client_a.get("/api/v1/jobs?status=discovered").json()
    theirs = client_b.get("/api/v1/jobs?status=discovered").json()
    assert len(own) == 3
    assert len(theirs) == 3
    assert {job["id"] for job in own}.isdisjoint({job["id"] for job in theirs})
    assert client_b.get(f"/api/v1/jobs/{own[0]['id']}").status_code == 404
    assert client_b.delete(f"/api/v1/jobs/{own[0]['id']}").status_code == 404

    db = TestingSessionLocal()
    counts = [row.request_count for row in db.query(JobProviderQuota).all()]
    db.close()
    assert counts == [1, 1]


def test_disabled_provider_is_skipped_and_its_discovered_jobs_are_removed():
    assert client.post("/api/v1/jobs/discovery").status_code == 200
    saved = client.put("/api/v1/jobs/discovery/settings", json={
        "providers": [{"provider_key": "jooble", "enabled": False}],
    })
    assert saved.status_code == 200
    jooble = next(item for item in saved.json()["providers"] if item["provider_key"] == "jooble")
    assert jooble["enabled"] is False
    assert jooble["status"] == "disabled"
    calls.clear()

    refreshed = client.post("/api/v1/jobs/discovery")
    assert refreshed.status_code == 200
    assert refreshed.json()["providers"][1]["status"] == "disabled" or any(
        item["status"] == "disabled" and item["provider_key"] == "jooble" for item in refreshed.json()["providers"]
    )
    assert all("jooble.org" not in str(call.url) for call in calls)
    titles = {job["title"] for job in client.get("/api/v1/jobs?status=discovered").json()}
    assert "Designer" not in titles
    assert "Software Engineer" in titles


def test_provider_toggle_is_private_to_the_user():
    saved = client_a.put("/api/v1/jobs/discovery/settings", json={
        "keywords": "SECRET-KEYWORDS",
        "location": "Dunedin",
        "country": "nz",
        "remote_preference": "remote",
        "providers": [{"provider_key": "seek", "enabled": False}],
    })
    assert saved.status_code == 200
    assert saved.json()["keywords"] == "SECRET-KEYWORDS"
    assert saved.json()["search"]["keywords"] == "SECRET-KEYWORDS remote"
    assert all(item["provider_key"] != "seek" for item in saved.json()["link_outs"])

    other = client_b.get("/api/v1/jobs/discovery/settings")
    assert other.status_code == 200
    assert other.json()["keywords"] == ""
    assert other.json()["location"] == "New Zealand"
    assert any(item["provider_key"] == "seek" and item["enabled"] is True for item in other.json()["providers"])
    assert client_a.get("/api/v1/jobs/discovery/settings").json()["keywords"] == "SECRET-KEYWORDS"


def test_missing_api_keys_skip_the_provider(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID")
    monkeypatch.delenv("ADZUNA_APP_KEY")
    monkeypatch.delenv("JOOBLE_API_KEY")
    response = client.get("/api/v1/jobs/discovery/settings")
    assert response.status_code == 200
    statuses = {item["provider_key"]: item["status"] for item in response.json()["providers"]}
    assert statuses["adzuna"] == "not_configured"
    assert statuses["jooble"] == "not_configured"
    assert statuses["seek"] == "ready"
    found = client.post("/api/v1/jobs/discovery")
    assert found.status_code == 200
    assert {item["status"] for item in found.json()["providers"]} == {"not_configured"}
    assert calls == []
    assert found.json()["created"] == 0


def test_daily_limit_skips_the_network_and_can_reuse_stale_listings(monkeypatch):
    monkeypatch.setenv("ADZUNA_DAILY_LIMIT", "0")
    monkeypatch.setenv("JOOBLE_DAILY_LIMIT", "0")
    blocked = client.post("/api/v1/jobs/discovery")
    assert blocked.status_code == 200
    assert {item["status"] for item in blocked.json()["providers"]} == {"rate_limited"}
    assert calls == []

    monkeypatch.setenv("ADZUNA_DAILY_LIMIT", "5")
    monkeypatch.setenv("JOOBLE_DAILY_LIMIT", "5")
    assert client.post("/api/v1/jobs/discovery").status_code == 200
    assert len(calls) == 2
    db = TestingSessionLocal()
    for row in db.query(JobProviderCache).all():
        row.fetched_at = row.fetched_at.replace(year=2020)
    db.commit()
    db.close()
    calls.clear()
    monkeypatch.setenv("ADZUNA_DAILY_LIMIT", "0")
    monkeypatch.setenv("JOOBLE_DAILY_LIMIT", "0")
    stale = client.post("/api/v1/jobs/discovery")
    assert stale.status_code == 200
    assert {item["status"] for item in stale.json()["providers"]} == {"rate_limited"}
    assert calls == []
    assert len(client.get("/api/v1/jobs?status=discovered").json()) == 3


def test_daily_refresh_does_not_call_providers_again_the_same_day(monkeypatch):
    monkeypatch.setenv("JOB_DISCOVERY_DAILY_SECONDS", "72000")
    assert client.post("/api/v1/jobs/discovery/refresh").status_code == 200
    assert len(calls) == 2
    second = client.post("/api/v1/jobs/discovery/refresh")
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert len(calls) == 2


def test_interactive_window_reruns_when_the_search_changes(monkeypatch):
    monkeypatch.setenv("JOB_DISCOVERY_INTERACTIVE_SECONDS", "3600")
    assert client.post("/api/v1/jobs/discovery").status_code == 200
    assert len(calls) == 2
    again = client.post("/api/v1/jobs/discovery")
    assert again.json()["cached"] is True
    assert len(calls) == 2
    changed = client.put("/api/v1/jobs/discovery/settings", json={"keywords": "nurse"})
    assert changed.status_code == 200
    rerun = client.post("/api/v1/jobs/discovery")
    assert rerun.json()["cached"] is False
    assert len(calls) == 4


def test_saved_job_with_the_same_url_is_not_duplicated():
    created = client.post("/api/v1/jobs", json={
        "title": "Software Engineer",
        "company": "Example NZ",
        "location": "Auckland",
        "url": "https://example.com/jobs/engineer",
        "description": "Kept by the user.",
    })
    assert created.status_code == 201
    found = client.post("/api/v1/jobs/discovery")
    assert found.status_code == 200
    assert found.json()["duplicates"] >= 1
    rows = client.get("/api/v1/jobs?status=all").json()
    engineer = [job for job in rows if job["url"] == "https://example.com/jobs/engineer"]
    assert len(engineer) == 1
    assert engineer[0]["status"] == "saved"
    assert engineer[0]["description"] == "Kept by the user."


def test_match_sort_puts_the_closer_role_first():
    db = TestingSessionLocal()
    db.add(CareerProfile(
        user_id=DEFAULT_USER_ID,
        headline="Software Engineer",
        location="Auckland",
        skills="Python, AWS",
    ))
    db.add(JobListing(
        user_id=DEFAULT_USER_ID,
        title="Nurse",
        location="Wellington",
        description="Ward nursing.",
        source="Adzuna",
        status="discovered",
    ))
    db.add(JobListing(
        user_id=DEFAULT_USER_ID,
        title="Software Engineer",
        location="Auckland",
        description="Build APIs with Python and AWS.",
        source="Adzuna",
        status="discovered",
    ))
    db.commit()
    db.close()
    listed = client.get("/api/v1/jobs?status=discovered&sort=match")
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Software Engineer"
    assert listed.json()[0]["match_score"] is not None
    detail = client.get(f"/api/v1/jobs/{listed.json()[0]['id']}")
    assert detail.status_code == 200
    assert "python" in detail.json()["match"]["matched_skills"]


def test_link_outs_use_the_profile_when_keywords_are_blank():
    db = TestingSessionLocal()
    db.add(CareerProfile(
        user_id=DEFAULT_USER_ID,
        headline="Product Designer",
        location="Wellington",
        skills="Figma",
    ))
    db.commit()
    db.close()
    settings = client.get("/api/v1/jobs/discovery/settings")
    assert settings.status_code == 200
    body = settings.json()
    assert body["search"]["keywords_from_profile"] is True
    assert body["search"]["keywords"] == "Product Designer Figma"
    seek = next(item for item in body["link_outs"] if item["provider_key"] == "seek")
    assert seek["url"].startswith("https://www.seek.co.nz/jobs?")
    assert "Product+Designer+Figma" in seek["url"]
    linkedin = next(item for item in body["link_outs"] if item["provider_key"] == "linkedin")
    assert "linkedin.com/jobs/search" in linkedin["url"]


def test_unknown_provider_is_rejected():
    response = client.put("/api/v1/jobs/discovery/settings", json={
        "providers": [{"provider_key": "secret-scraper", "enabled": True}],
    })
    assert response.status_code == 422


def test_discovery_requires_a_user():
    raw = TestClient(app)
    assert raw.get("/api/v1/jobs/discovery/settings").status_code == 401
    assert raw.post("/api/v1/jobs/discovery").status_code == 401
    assert raw.post("/api/v1/jobs/discovery/refresh").status_code == 401
    assert raw.post("/api/v1/jobs/from-link", json={"url": "https://example.com/job"}).status_code == 401


def test_seek_link_requires_a_pasted_description_and_is_not_fetched():
    refused = client.post("/api/v1/jobs/from-link", json={"url": "https://www.seek.co.nz/job/123456"})
    assert refused.status_code == 422
    assert "Paste the job description" in refused.json()["detail"]
    assert calls == []
    saved = client.post("/api/v1/jobs/from-link", json={
        "url": "https://www.seek.co.nz/job/123456",
        "title": "Registered Nurse",
        "company": "Care Co",
        "location": "Wellington",
        "description": "Provide ward care and mentor new graduates.",
    })
    assert saved.status_code == 201
    assert saved.json()["source"] == "SEEK"
    assert saved.json()["status"] == "saved"
    assert calls == []
    duplicate = client.post("/api/v1/jobs/from-link", json={
        "url": "https://www.seek.co.nz/job/123456",
        "description": "Provide ward care and mentor new graduates.",
    })
    assert duplicate.status_code == 409


def test_other_public_pages_can_be_read_from_json_ld():
    saved = client.post("/api/v1/jobs/from-link", json={"url": "https://jobs.example/role"})
    assert saved.status_code == 201
    body = saved.json()
    assert body["title"] == "Platform Engineer"
    assert body["company"] == "Harbour Labs"
    assert "Python" in body["description"]
    assert body["source"] == "Added from link"
    assert body["location"].startswith("Auckland")
    assert len(calls) == 1
    other = client_b.get(f"/api/v1/jobs/{body['id']}")
    assert other.status_code == 404


def test_private_and_redirected_links_are_not_downloaded():
    private = client.post("/api/v1/jobs/from-link", json={"url": "http://127.0.0.1/latest/meta-data"})
    assert private.status_code == 422
    assert calls == []
    redirected = client.post("/api/v1/jobs/from-link", json={"url": "https://jobs.example/go"})
    assert redirected.status_code == 422
    assert len(calls) == 1
    assert calls[0].url.path == "/go"
