from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from io import BytesIO
import re

from app.database import get_db
from app.models import CvDocument
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
