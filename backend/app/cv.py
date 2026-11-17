from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from io import BytesIO
import re

from app.database import get_db
from app.models import CvDocument, CvVersion
from app.cv_export import build_docx, build_pdf

router = APIRouter(prefix="/api/v1/cv", tags=["CV Studio"])


class CvPayload(BaseModel):
    name: str = Field(default="", max_length=160)
    headline: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=5000)
    experience: str = Field(default="", max_length=15000)
    skills: str = Field(default="", max_length=5000)
    education: str = Field(default="", max_length=8000)


class CvResponse(CvPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int


@router.get("", response_model=CvResponse)
def get_cv(db: Session = Depends(get_db)) -> CvDocument:
    cv = db.get(CvDocument, 1)
    if cv is None:
        cv = CvDocument(id=1)
        db.add(cv)
        db.commit()
        db.refresh(cv)
    return cv


@router.put("", response_model=CvResponse)
def save_cv(payload: CvPayload, db: Session = Depends(get_db)) -> CvDocument:
    cv = db.get(CvDocument, 1)
    if cv is None:
        cv = CvDocument(id=1, **payload.model_dump())
        db.add(cv)
    else:
        for key, value in payload.model_dump().items():
            setattr(cv, key, value)
    db.commit()
    db.refresh(cv)
    return cv


@router.post("/export")
def export_cv(
    format: str = Query(pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    cv = db.get(CvDocument, 1)
    if cv is None:
        raise HTTPException(status_code=404, detail="Save your CV before exporting it.")

    if not any((cv.name, cv.headline, cv.summary, cv.experience, cv.skills, cv.education)):
        raise HTTPException(status_code=400, detail="Add some CV content before exporting.")

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", cv.name.strip()).strip("-") or "CareerPilot-CV"
    if format == "pdf":
        content = build_pdf(cv)
        media_type = "application/pdf"
        filename = f"{safe_name}-CV.pdf"
    else:
        content = build_docx(cv)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{safe_name}-CV.docx"

    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class CvVersionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    job_title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)


class CvVersionResponse(BaseModel):
    id: int
    label: str
    job_title: str
    company: str
    notes: str
    snapshot: CvPayload
    created_at: str


@router.get("/versions", response_model=list[CvVersionResponse])
def list_cv_versions(db: Session = Depends(get_db)) -> list[dict]:
    versions = db.query(CvVersion).order_by(CvVersion.created_at.desc(), CvVersion.id.desc()).all()
    return [
        {
            "id": version.id,
            "label": version.label,
            "job_title": version.job_title,
            "company": version.company,
            "notes": version.notes,
            "snapshot": version.snapshot,
            "created_at": version.created_at.isoformat(),
        }
        for version in versions
    ]


@router.post("/versions", response_model=CvVersionResponse, status_code=201)
def create_cv_version(payload: CvVersionCreate, db: Session = Depends(get_db)) -> dict:
    cv = db.get(CvDocument, 1)
    if cv is None or not any((cv.name, cv.headline, cv.summary, cv.experience, cv.skills, cv.education)):
        raise HTTPException(status_code=400, detail="Add and save CV content before creating a version.")

    version = CvVersion(
        label=payload.label.strip(),
        job_title=payload.job_title.strip(),
        company=payload.company.strip(),
        notes=payload.notes.strip(),
        snapshot={
            "name": cv.name,
            "headline": cv.headline,
            "summary": cv.summary,
            "experience": cv.experience,
            "skills": cv.skills,
            "education": cv.education,
        },
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return {
        "id": version.id,
        "label": version.label,
        "job_title": version.job_title,
        "company": version.company,
        "notes": version.notes,
        "snapshot": version.snapshot,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/versions/{version_id}", response_model=CvVersionResponse)
def get_cv_version(version_id: int, db: Session = Depends(get_db)) -> dict:
    version = db.get(CvVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="CV version not found.")
    return {
        "id": version.id,
        "label": version.label,
        "job_title": version.job_title,
        "company": version.company,
        "notes": version.notes,
        "snapshot": version.snapshot,
        "created_at": version.created_at.isoformat(),
    }


@router.post("/versions/{version_id}/restore", response_model=CvResponse)
def restore_cv_version(version_id: int, db: Session = Depends(get_db)) -> CvDocument:
    version = db.get(CvVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="CV version not found.")

    cv = db.get(CvDocument, 1)
    if cv is None:
        cv = CvDocument(id=1, **version.snapshot)
        db.add(cv)
    else:
        for key, value in version.snapshot.items():
            setattr(cv, key, value)
    db.commit()
    db.refresh(cv)
    return cv
