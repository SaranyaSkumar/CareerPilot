"""Provider parsing, dedupe, link-out URLs, and the public-page reader."""

import ipaddress

import pytest

from app.job_providers.adzuna import parse_adzuna_results
from app.job_providers.jooble import jooble_endpoint, parse_jooble_results
from app.job_providers.linkouts import indeed_url, linkedin_url, seek_url, trademe_url
from app.job_providers.page_fetch import (
    PASTE_INSTEAD,
    PASTE_REQUIRED,
    PUBLIC_LINK,
    FetchError,
    assert_public_http_url,
    host_is_blocked,
    parse_public_job_page,
    set_resolver,
)
from app.job_providers.types import SearchQuery, canonical_url, dedupe_jobs, dedupe_key, NormalizedJob
from migrations.sql_script import split_sql


def query(**overrides) -> SearchQuery:
    values = {"keywords": "Product Designer", "location": "Wellington", "country": "nz", "remote": "any"}
    values.update(overrides)
    return SearchQuery(**values)


def test_dedupe_key_ignores_case_and_punctuation():
    left = dedupe_key("Senior Software Engineer!", "Example NZ", "Auckland")
    right = dedupe_key("  senior   software engineer", "example nz", "Auckland,")
    assert left == right
    assert dedupe_key("Nurse", "Care Co", "Wellington") != left


def test_canonical_url_drops_tracking_and_trailing_slash():
    assert canonical_url("HTTPS://Example.com/jobs/1/?utm_source=adzuna&b=2") == "https://example.com/jobs/1?b=2"


def test_dedupe_jobs_collapses_url_and_title_company_location():
    jobs = dedupe_jobs([
        NormalizedJob(title="Engineer", company="Example", location="Auckland", source="Adzuna", url="https://example.com/a"),
        NormalizedJob(title="engineer", company="Example", location="Auckland", source="Jooble", url="https://other.example/a"),
        NormalizedJob(title="Nurse", company="Care", location="Wellington", source="Jooble", url="https://example.com/a/"),
    ])
    assert [job.source for job in jobs] == ["Adzuna"]
    assert jobs[0].title == "Engineer"


def test_adzuna_parser_normalises_salary_and_skips_incomplete_rows():
    jobs = parse_adzuna_results({
        "results": [
            {
                "title": "Software Engineer",
                "redirect_url": "https://example.com/jobs/1",
                "company": {"display_name": "Example NZ"},
                "location": {"display_name": "Auckland"},
                "description": "Build <b>Python</b> APIs.",
                "created": "2026-11-01T00:00:00Z",
                "salary_min": 90000,
                "salary_max": 120000,
                "salary_is_predicted": 0,
            },
            {"title": "", "redirect_url": "https://example.com/missing"},
            {
                "title": "Estimated role",
                "redirect_url": "https://example.com/jobs/2",
                "salary_min": 80000,
                "salary_is_predicted": 1,
                "description": "Work",
            },
        ]
    }, fallback_location="New Zealand", country="nz")
    assert len(jobs) == 2
    assert jobs[0].company == "Example NZ"
    assert jobs[0].salary == "NZD 90,000–120,000"
    assert "Python" in jobs[0].description
    assert "<b>" not in jobs[0].description
    assert jobs[0].posted_at is not None
    assert jobs[1].salary.endswith("(estimated)")


def test_jooble_parser_reads_the_documented_payload():
    jobs = parse_jooble_results({
        "totalCount": 1,
        "jobs": [{
            "id": 123,
            "title": "Sales Manager",
            "location": "Auckland",
            "snippet": "This is a <b>great</b> opportunity.",
            "salary": "80,000 - 90,000 NZD",
            "source": "board",
            "type": "Full-time",
            "link": "https://nz.jooble.org/jdp/123",
            "company": "ABC Corp",
            "updated": "2023-09-15T12:55:35.3870000",
        }],
    }, fallback_location="New Zealand")
    assert jobs[0].source == "Jooble"
    assert jobs[0].company == "ABC Corp"
    assert jobs[0].salary == "80,000 - 90,000 NZD"
    assert "great" in jobs[0].description
    assert jobs[0].description.startswith("Full-time")
    assert jobs[0].posted_at is not None
    assert jobs[0].posted_at.year == 2023


def test_jooble_endpoint_stays_on_an_official_host(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "abc123key")
    monkeypatch.setenv("JOOBLE_API_BASE", "https://nz.jooble.org/api")
    assert jooble_endpoint() == "https://nz.jooble.org/api/abc123key"
    monkeypatch.setenv("JOOBLE_API_BASE", "http://127.0.0.1/api")
    with pytest.raises(Exception, match="not configured"):
        jooble_endpoint()


def test_link_out_urls_are_prefilled_new_zealand_searches():
    remote = query(remote="remote", location="Auckland")
    assert seek_url(remote) == "https://www.seek.co.nz/jobs?keywords=Product+Designer+remote&where=Auckland"
    assert "f_WT=2" in linkedin_url(remote)
    assert "Auckland" in linkedin_url(remote)
    assert indeed_url(query()) == "https://nz.indeed.com/jobs?q=Product+Designer&l=Wellington"
    onsite = query(remote="onsite")
    assert "f_WT=1" in linkedin_url(onsite)
    trade = trademe_url(query())
    assert trade.startswith("https://www.trademe.co.nz/a/jobs/search?")
    assert "Wellington" in trade


def test_blocked_boards_and_private_addresses_are_not_fetched():
    assert host_is_blocked("www.seek.co.nz")
    assert host_is_blocked("nz.indeed.com")
    assert host_is_blocked("jobs.linkedin.com")
    assert not host_is_blocked("jobs.example")
    with pytest.raises(FetchError, match=PASTE_REQUIRED):
        assert_public_http_url("https://www.seek.co.nz/job/123")
    with pytest.raises(FetchError, match=PASTE_INSTEAD):
        assert_public_http_url("http://127.0.0.1/latest")
    with pytest.raises(FetchError, match=PUBLIC_LINK):
        assert_public_http_url("javascript:alert(1)")
    set_resolver(lambda _host: [ipaddress.ip_address("10.1.1.1")])
    try:
        with pytest.raises(FetchError, match=PASTE_INSTEAD):
            assert_public_http_url("https://internal.example/job")
    finally:
        set_resolver(None)


def test_public_page_parser_prefers_jobposting_json_ld():
    page = """
    <html><head>
      <title>Ignored | Example</title>
      <script type="application/ld+json">
        {"@graph":[
          {"@type":"Organization","name":"Nope"},
          {"@type":"JobPosting","title":"Platform Engineer","description":"<p>Build Python services.</p>",
           "hiringOrganization":{"name":"Harbour Labs"},
           "jobLocation":{"address":{"addressLocality":"Auckland","addressCountry":"NZ"}},
           "datePosted":"2026-11-10",
           "baseSalary":{"currency":"NZD","value":{"minValue":100000,"maxValue":130000,"unitText":"YEAR"}}}
        ]}
      </script>
    </head></html>
    """
    parsed = parse_public_job_page(page)
    assert parsed["title"] == "Platform Engineer"
    assert parsed["company"] == "Harbour Labs"
    assert parsed["location"] == "Auckland, NZ"
    assert "Build Python services." in parsed["description"]
    assert "NZD" in parsed["salary"]
    assert parsed["posted_at"] is not None


def test_public_page_parser_falls_back_to_title_and_meta_description():
    page = """
    <html><head>
      <title>Coordinator | Example</title>
      <meta name="description" content="Coordinate the team.">
    </head></html>
    """
    parsed = parse_public_job_page(page)
    assert parsed["title"] == "Coordinator"
    assert parsed["description"] == "Coordinate the team."


def test_discovery_sql_enforces_owner_access_and_revokes_extra_privileges():
    from pathlib import Path

    script = Path("migrations_sql/20261117_0005_job_discovery.sql").read_text(encoding="utf-8")
    migration = Path("migrations/versions/20261117_0005_job_discovery.py").read_text(encoding="utf-8")
    assert 'revision = "20261117_0005"' in migration
    assert 'down_revision = "20261117_0004"' in migration
    statements = split_sql(script)
    assert any("CREATE TABLE job_discovery_settings" in statement for statement in statements)
    assert any("CREATE TABLE job_provider_settings" in statement for statement in statements)
    assert "ENABLE ROW LEVEL SECURITY" in script
    assert "(SELECT auth.uid()) = user_id" in script
    assert "careerpilot_app" in script
    assert "TRUNCATE" in script
    assert "REFERENCES" in script
    assert "TRIGGER" in script
    assert "FROM anon" in script
    assert "TO anon" not in script
    assert "job_provider_cache" in script
    assert "job_provider_quota" in script
