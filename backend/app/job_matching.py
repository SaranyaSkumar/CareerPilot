import re

from app.models import CareerProfile, CvDocument, JobListing

# A transparent, deliberately limited vocabulary. Expand this list as the product
# gains tested aliases; never infer that an unlisted skill is absent.
SKILL_ALIASES = {
    "python": ("python",),
    "typescript": ("typescript",),
    "javascript": ("javascript", "ecmascript"),
    "react": ("react", "react.js"),
    "next.js": ("next.js", "nextjs"),
    "node.js": ("node.js", "nodejs"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure",),
    "gcp": ("gcp", "google cloud"),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "sql": ("sql",),
    "postgresql": ("postgresql", "postgres"),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "terraform": ("terraform",),
    "linux": ("linux",),
    "git": ("git",),
    "github actions": ("github actions",),
    "ci/cd": ("ci/cd", "continuous integration", "continuous delivery"),
    "java": ("java",),
    "c#": ("c#", "c sharp"),
    ".net": (".net", "dotnet"),
    "go": ("golang",),
    "rust": ("rust",),
    "graphql": ("graphql",),
    "rest api": ("rest api", "restful api"),
    "html": ("html",),
    "css": ("css",),
    "tailwind css": ("tailwind",),
    "angular": ("angular",),
    "vue": ("vue", "vue.js"),
    "express": ("express", "express.js"),
    "pandas": ("pandas",),
    "machine learning": ("machine learning",),
    "data analysis": ("data analysis",),
    "agile": ("agile",),
    "scrum": ("scrum",),
}

def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])", text.lower()))

def _detected_skills(text: str) -> set[str]:
    return {
        skill for skill, aliases in SKILL_ALIASES.items()
        if any(_contains(text, alias) for alias in aliases)
    }

def analyse_job_match(job: JobListing, profile: CareerProfile | None, cv: CvDocument | None) -> dict:
    profile = profile or CareerProfile(id=1)
    cv = cv or CvDocument(id=1)
    candidate_text = " ".join([
        profile.headline or "", profile.summary or "", profile.skills or "",
        cv.headline or "", cv.summary or "", cv.experience or "", cv.skills or "",
    ])
    job_text = " ".join([job.title or "", job.description or ""])
    candidate_skills = _detected_skills(candidate_text)
    job_skills = _detected_skills(job_text)
    matched = sorted(candidate_skills & job_skills)
    missing = sorted(job_skills - candidate_skills)
    unknown_candidate = not candidate_text.strip()
    has_job_requirements = bool(job_skills)

    skill_score = round((len(matched) / len(job_skills)) * 70) if job_skills else 0
    title_tokens = {
        token for token in re.findall(r"[a-z][a-z0-9+#.]{2,}", (job.title or "").lower())
        if token not in {"senior", "junior", "lead", "engineer", "developer", "software", "the", "and"}
    }
    candidate_tokens = set(re.findall(r"[a-z][a-z0-9+#.]{2,}", (profile.headline or cv.headline or "").lower()))
    role_overlap = len(title_tokens & candidate_tokens)
    role_score = min(20, round(20 * role_overlap / max(1, len(title_tokens)))) if title_tokens else 0

    preferred_location = (profile.location or "").strip().lower()
    job_location = (job.location or "").strip().lower()
    if not preferred_location or not job_location:
        location_score = 5
        location_reason = "Location preference or vacancy location is incomplete."
    elif preferred_location in job_location or job_location in preferred_location:
        location_score = 10
        location_reason = "The vacancy location matches your saved location preference."
    elif "new zealand" in preferred_location and ("new zealand" in job_location or "remote" in job_location):
        location_score = 10
        location_reason = "The vacancy appears to be within your saved New Zealand preference."
    else:
        location_score = 0
        location_reason = "The vacancy location differs from your saved preference; check flexibility."

    score = skill_score + role_score + location_score
    return {
        "score": score,
        "label": "Strong alignment" if score >= 70 else "Some alignment" if score >= 40 else "Limited evidence of alignment",
        "components": [
            {"name": "Relevant skills", "score": skill_score, "out_of": 70, "detail": f"{len(matched)} of {len(job_skills)} detected job skills also appear in your saved profile or CV." if has_job_requirements else "No recognised skills found in the saved job description."},
            {"name": "Role alignment", "score": role_score, "out_of": 20, "detail": f"{role_overlap} role-related title terms overlap with your saved headline." if title_tokens else "The job title does not provide enough role terms to compare."},
            {"name": "Location", "score": location_score, "out_of": 10, "detail": location_reason},
        ],
        "matched_skills": matched,
        "not_found_in_profile": missing,
        "limitations": [
            "This is a deterministic indicator based only on text saved in CareerPilot, not an AI assessment or a prediction of hiring outcomes.",
            "A skill not found in your profile or CV is not proof that you do not have it.",
            "The current skill dictionary is intentionally limited; review the original job description yourself.",
        ] + (["Add your verified skills and experience to your Career Profile or CV for a more useful comparison."] if unknown_candidate else []),
    }
