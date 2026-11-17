import re

from app.models import CareerProfile, JobListing

# Curated, transparent vocabulary. This is intentionally rules-based; unknown terms
# are not treated as missing skills and no external model or embedding is used.
KNOWN_SKILLS = {
    "aws", "azure", "gcp", "python", "javascript", "typescript", "java", "c#", "go",
    "rust", "node.js", "nodejs", "react", "next.js", "nextjs", "angular", "vue",
    "fastapi", "django", "flask", "express", "sql", "postgresql", "mysql", "mongodb",
    "redis", "docker", "kubernetes", "terraform", "cloudformation", "serverless",
    "lambda", "ci/cd", "github actions", "git", "linux", "html", "css", "tailwind",
    "rest api", "graphql", "microservices", "agile", "scrum", "pytest", "playwright",
    "selenium", "jest", "cypress", "machine learning", "data analysis", "power bi",
    "communication", "leadership", "project management",
}


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _skill_list(value: str) -> list[str]:
    parts = re.split(r"[,;\n|]+", value or "")
    result = []
    seen = set()
    for part in parts:
        skill = _normalise(part)
        if skill and skill not in seen:
            seen.add(skill)
            result.append(skill)
    return result


def analyse_job_fit(job: JobListing, profile: CareerProfile) -> dict:
    description = _normalise(f"{job.title} {job.description}")
    candidate_skills = _skill_list(profile.skills)
    matched = [skill for skill in candidate_skills if skill in description]
    not_found = [skill for skill in candidate_skills if skill not in description]

    detected_requirements = [
        skill for skill in sorted(KNOWN_SKILLS)
        if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", description)
    ]
    candidate_normalised = " " + " ".join(candidate_skills) + " "
    required_matched = [
        skill for skill in detected_requirements
        if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", candidate_normalised)
    ]
    required_missing = [skill for skill in detected_requirements if skill not in required_matched]

    if detected_requirements:
        skills_score = round(len(required_matched) / len(detected_requirements) * 70)
    else:
        skills_score = None

    headline_tokens = {
        token for token in re.findall(r"[a-z0-9+#.]+", _normalise(profile.headline))
        if len(token) > 2
    }
    title_tokens = {
        token for token in re.findall(r"[a-z0-9+#.]+", _normalise(job.title))
        if len(token) > 2
    }
    role_score = round(len(headline_tokens & title_tokens) / len(title_tokens) * 20) if title_tokens else 0

    profile_location = _normalise(profile.location)
    job_location = _normalise(job.location)
    location_match = bool(profile_location and job_location and (
        profile_location in job_location or job_location in profile_location
        or "remote" in job_location
    ))
    location_score = 10 if location_match else 0

    score = min(100, skills_score + role_score + location_score) if skills_score is not None else None
    return {
        "job_id": job.id,
        "score": score,
        "skills_score": skills_score,
        "role_score": role_score,
        "location_score": location_score,
        "matched_skills": required_matched,
        "not_found_skills": required_missing,
        "candidate_skills_mentioned": matched,
        "candidate_skills_not_mentioned": not_found,
        "detected_requirement_count": len(detected_requirements),
        "profile_ready": bool(candidate_skills and profile.headline.strip()),
        "message": (
            "Indicative rules-based comparison, not a hiring prediction. "
            "A skill not found in the description may still be relevant; unknown terms are not scored."
        ),
    }
