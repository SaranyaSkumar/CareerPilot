from __future__ import annotations

import re
import uuid
from collections import Counter
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import CvDocument

router = APIRouter(prefix="/api/v1/cv", tags=["CV Studio"])

class AnalysisRequest(BaseModel):
    job_description: str = Field(default="", max_length=20000)

class Finding(BaseModel):
    code: str
    severity: Literal["info", "warning", "good"]
    title: str
    detail: str

class KeywordResult(BaseModel):
    term: str
    status: Literal["matched", "related", "missing"]
    evidence: str = ""

class AnalysisResponse(BaseModel):
    formatting_score: int
    content_score: int | None
    overall_score: int | None
    findings: list[Finding]
    keywords: list[KeywordResult]
    disclaimer: str

STOP_WORDS = {
    "about", "above", "after", "again", "against", "also", "among", "and", "are", "because",
    "been", "being", "below", "between", "both", "could", "demonstrate", "desired", "develop",
    "each", "ensure", "excellent", "experience", "from", "have", "into", "including", "looking",
    "must", "our", "over", "preferred", "provide", "role", "should", "that", "their", "this",
    "those", "through", "under", "using", "various", "what", "when", "where", "which", "while",
    "will", "with", "work", "years", "your", "you", "team", "teams", "such", "well", "strong",
    "skills", "ability", "responsibilities", "requirements", "qualification", "qualifications",
    "candidate", "position", "company", "opportunity", "knowledge", "including", "across",
}
TECH_TERMS = {
    "python", "typescript", "javascript", "java", "c#", "c++", "go", "golang", "rust", "ruby",
    "php", "sql", "postgresql", "mysql", "mongodb", "redis", "aws", "azure", "gcp", "docker",
    "kubernetes", "terraform", "cloudformation", "lambda", "serverless", "react", "next.js",
    "angular", "vue", "node.js", "fastapi", "django", "flask", "express", "graphql", "rest",
    "api", "git", "github", "ci/cd", "linux", "agile", "scrum", "microservices", "pytest",
    "playwright", "selenium", "html", "css", "tailwind", "machine learning", "llm", "rag",
}

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def _extract_terms(job_description: str) -> list[str]:
    text = _normalise(job_description)
    found = []
    for term in sorted(TECH_TERMS, key=len, reverse=True):
        if re.search(r"(?<![\w])" + re.escape(term) + r"(?![\w])", text):
            found.append(term)
    words = re.findall(r"[a-z][a-z0-9+#./-]{2,}", text)
    counts = Counter(word for word in words if word not in STOP_WORDS and word not in TECH_TERMS)
    found.extend(word for word, count in counts.most_common(12) if count >= 2)
    return list(dict.fromkeys(found))[:30]

def analyse_cv(cv, job_description: str = "") -> AnalysisResponse:
    fields = {
        "name": (cv.name or "").strip(),
        "headline": (cv.headline or "").strip(),
        "summary": (cv.summary or "").strip(),
        "experience": (cv.experience or "").strip(),
        "skills": (cv.skills or "").strip(),
        "education": (cv.education or "").strip(),
    }
    findings: list[Finding] = []
    checks = [
        ("name", "Add your name", "A clear name helps identify the document."),
        ("headline", "Add a professional headline", "A target role or professional title makes your direction clear."),
        ("summary", "Add a professional summary", "A concise summary gives readers context about your background."),
        ("experience", "Add work experience", "Include relevant roles, employers, dates and evidence-backed outcomes."),
        ("skills", "Add a skills section", "List skills you can confidently discuss and demonstrate."),
        ("education", "Add education or relevant training", "Include relevant qualifications, institutions and dates."),
    ]
    missing = [item for item in checks if not fields[item[0]]]
    for field, title, detail in missing:
        findings.append(Finding(code=f"missing_{field}", severity="warning", title=title, detail=detail))
    if fields["experience"] and not re.search(r"\b(19|20)\d{2}\b|\b(present|current)\b", fields["experience"], re.I):
        findings.append(Finding(code="dates", severity="warning", title="Check experience dates", detail="No obvious year or present/current marker was detected in the experience text. Confirm that each role has clear dates."))
    if fields["experience"] and len(fields["experience"].splitlines()) < 2:
        findings.append(Finding(code="experience_detail", severity="info", title="Make experience easy to scan", detail="Consider separating roles and achievements into distinct lines or bullet points."))

    all_text = " ".join(fields.values())
    if len(all_text) > 0:
        findings.append(Finding(code="plain_text", severity="good", title="Text-based CV content detected", detail="The editor stores selectable text. Keep the exported document text-based and avoid decorative graphics that carry essential information."))
    findings.append(Finding(code="layout_limit", severity="info", title="Layout checks are limited", detail="This analysis checks the structured CV text, not the final PDF/DOCX internals. It cannot verify columns, tables, headers, footers, fonts or parsing by a specific ATS."))

    formatting_score = max(0, min(100, 100 - len(missing) * 13 - (12 if fields["experience"] and not re.search(r"\b(19|20)\d{2}\b|\b(present|current)\b", fields["experience"], re.I) else 0) - (8 if fields["experience"] and len(fields["experience"].splitlines()) < 2 else 0)))
    if not missing:
        findings.append(Finding(code="core_sections", severity="good", title="Core CV sections are present", detail="All six structured CV fields contain content."))

    keywords: list[KeywordResult] = []
    content_score = None
    overall_score = None
    if job_description.strip():
        cv_text = _normalise(all_text)
        for term in _extract_terms(job_description):
            if re.search(r"(?<![\w])" + re.escape(term) + r"(?![\w])", cv_text):
                keywords.append(KeywordResult(term=term, status="matched", evidence="The term appears in your current CV text."))
            else:
                keywords.append(KeywordResult(term=term, status="missing", evidence="Not found in the current CV text. This does not prove you lack this skill or experience."))
        if keywords:
            matched = sum(item.status == "matched" for item in keywords)
            content_score = round(100 * matched / len(keywords))
            overall_score = round(formatting_score * 0.4 + content_score * 0.6)
        findings.append(Finding(code="job_alignment", severity="info", title="Job description comparison", detail="Keyword presence is a starting point only. Review each requirement for context and add wording only when it accurately reflects your experience."))
    else:
        findings.append(Finding(code="add_job_description", severity="info", title="Add a job description for a tailored check", detail="You can run this general CV check without a job description. Paste a role description to see keyword coverage and a job-alignment score."))

    return AnalysisResponse(
        formatting_score=formatting_score,
        content_score=content_score,
        overall_score=overall_score,
        findings=findings,
        keywords=keywords,
        disclaimer="CareerPilot's score is an indicative checklist, not an actual score from a proprietary ATS and not a prediction or guarantee of hiring outcomes. Missing keywords are not proof that you lack a skill.",
    )

@router.post("/analyse", response_model=AnalysisResponse)
def analyse_cv_endpoint(
    payload: AnalysisRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    cv = db.query(CvDocument).filter(CvDocument.user_id == user_id).one_or_none()
    if cv is None:
        cv = SimpleNamespace(name="", headline="", summary="", experience="", skills="", education="")
    return analyse_cv(cv, payload.job_description)
