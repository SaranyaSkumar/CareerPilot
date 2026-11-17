from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from io import BytesIO
import re
import uuid

from app.auth import get_current_user_id
from app.database import get_db
from app.models import CvDocument, CvVersion
from app.cv_export import build_docx, build_pdf
from app.ownership import get_or_create_for_user

router = APIRouter(prefix="/api/v1/cv", tags=["CV Studio"])

CV_FIELDS = ("name", "headline", "summary", "experience", "skills", "education")


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
def get_cv(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvDocument:
    return get_or_create_for_user(db, CvDocument, user_id)


@router.put("", response_model=CvResponse)
def save_cv(
    payload: CvPayload,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvDocument:
    cv = get_or_create_for_user(db, CvDocument, user_id)
    for key, value in payload.model_dump().items():
        setattr(cv, key, value)
    db.commit()
    db.refresh(cv)
    return cv


@router.post("/export")
def export_cv(
    format: str = Query(pattern="^(pdf|docx)$"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    cv = db.query(CvDocument).filter(CvDocument.user_id == user_id).one_or_none()
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


def _version_payload(version: CvVersion) -> dict:
    return {
        "id": version.id,
        "label": version.label,
        "job_title": version.job_title,
        "company": version.company,
        "notes": version.notes,
        "snapshot": version.snapshot,
        "created_at": version.created_at.isoformat(),
    }


def _own_version(db: Session, user_id: uuid.UUID, version_id: int) -> CvVersion:
    version = (
        db.query(CvVersion)
        .filter(CvVersion.id == version_id, CvVersion.user_id == user_id)
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="CV version not found.")
    return version


@router.get("/versions", response_model=list[CvVersionResponse])
def list_cv_versions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[dict]:
    versions = (
        db.query(CvVersion)
        .filter(CvVersion.user_id == user_id)
        .order_by(CvVersion.created_at.desc(), CvVersion.id.desc())
        .all()
    )
    return [_version_payload(version) for version in versions]


@router.post("/versions", response_model=CvVersionResponse, status_code=201)
def create_cv_version(
    payload: CvVersionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    cv = db.query(CvDocument).filter(CvDocument.user_id == user_id).one_or_none()
    if cv is None or not any(getattr(cv, field) for field in CV_FIELDS):
        raise HTTPException(status_code=400, detail="Add and save CV content before creating a version.")

    version = CvVersion(
        user_id=user_id,
        label=payload.label.strip(),
        job_title=payload.job_title.strip(),
        company=payload.company.strip(),
        notes=payload.notes.strip(),
        snapshot={field: getattr(cv, field) for field in CV_FIELDS},
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_payload(version)


@router.get("/versions/{version_id}", response_model=CvVersionResponse)
def get_cv_version(
    version_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    return _version_payload(_own_version(db, user_id, version_id))


@router.post("/versions/{version_id}/restore", response_model=CvResponse)
def restore_cv_version(
    version_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvDocument:
    version = _own_version(db, user_id, version_id)
    cv = get_or_create_for_user(db, CvDocument, user_id)
    snapshot = version.snapshot if isinstance(version.snapshot, dict) else {}
    for field in CV_FIELDS:
        setattr(cv, field, snapshot.get(field, ""))
    db.commit()
    db.refresh(cv)
    return cv
