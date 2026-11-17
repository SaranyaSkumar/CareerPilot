from app.models import CareerProfile, JobListing
from app.jobs_matching import analyse_job_fit


def test_job_fit_reports_matched_and_not_found_skills():
    profile = CareerProfile(
        headline="Software Engineer",
        location="Auckland, New Zealand",
        skills="Python, AWS, React, PostgreSQL",
    )
    job = JobListing(
        id=7,
        title="Software Engineer",
        location="Auckland",
        description="Build APIs with Python and AWS. Experience with Docker is useful.",
    )

    result = analyse_job_fit(job, profile)

    assert result["score"] is not None
    assert "python" in result["matched_skills"]
    assert "aws" in result["matched_skills"]
    assert "docker" in result["not_found_skills"]
    assert result["location_score"] == 10


def test_job_fit_does_not_invent_requirements_when_description_has_no_known_skills():
    profile = CareerProfile(headline="Software Engineer", location="Wellington", skills="Python")
    job = JobListing(id=8, title="Operations Coordinator", location="Auckland", description="Coordinate daily operations.")

    result = analyse_job_fit(job, profile)

    assert result["score"] is None
    assert result["detected_requirement_count"] == 0
