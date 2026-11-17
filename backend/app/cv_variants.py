"""Named CV variants.

The original cv_documents row stays the master draft. A tailored CV is stored
here instead of replacing that draft. Export and ATS analysis can target any
variant the caller owns.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.cv import CV_FIELDS, CvPayload, _contact_for_user
from app.cv_analysis import AnalysisResponse, analyse_cv
from app.cv_export import build_docx, build_pdf
from app.database import get_db
from app.models import CvDocument, CvVariant, JobListing

router = APIRouter(prefix="/api/v1/cv/variants", tags=["CV Studio"])


class VariantCreate(CvPayload):
    label: str = Field(min_length=1, max_length=160)
    job_title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    job_id: int | None = Field(default=None, ge=1)
    job_description: str = Field(default="", max_length=20000)


class VariantUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    job_title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)


class VariantResponse(CvPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    job_title: str
    company: str
    job_id: int | None
    job_description: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ScoreRequest(CvPayload):
    job_description: str = Field(default="", max_length=20000)


class VariantAnalysis(BaseModel):
    variant: AnalysisResponse
    original: AnalysisResponse


def _own_variant(db: Session, user_id: uuid.UUID, variant_id: int) -> CvVariant:
    variant = (
        db.query(CvVariant)
        .filter(CvVariant.id == variant_id, CvVariant.user_id == user_id)
        .one_or_none()
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="CV variant not found.")
    return variant


def _clear_default(db: Session, user_id: uuid.UUID) -> None:
    rows = (
        db.query(CvVariant)
        .filter(CvVariant.user_id == user_id, CvVariant.is_default.is_(True))
        .all()
    )
    for row in rows:
        row.is_default = False


def _content_namespace(source) -> SimpleNamespace:
    return SimpleNamespace(**{field: getattr(source, field, "") or "" for field in CV_FIELDS})


def variant_label(job_title: str, company: str) -> str:
    role = job_title.strip() or "role"
    company_name = company.strip()
    label = f"Tailored – {role} @ {company_name}" if company_name else f"Tailored – {role}"
    return label[:160]


@router.get("", response_model=list[VariantResponse])
def list_variants(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[CvVariant]:
    return (
        db.query(CvVariant)
        .filter(CvVariant.user_id == user_id)
        .order_by(CvVariant.is_default.desc(), CvVariant.updated_at.desc(), CvVariant.id.desc())
        .all()
    )


@router.post("/score", response_model=AnalysisResponse)
def score_draft(
    payload: ScoreRequest,
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> AnalysisResponse:
    """Score a draft that has not been saved. Does not call a model or write."""

    return analyse_cv(_content_namespace(payload), payload.job_description)


@router.post("/clear-default", response_model=list[VariantResponse])
def clear_default(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[CvVariant]:
    _clear_default(db, user_id)
    db.commit()
    return list_variants(user_id=user_id, db=db)


@router.post("", response_model=VariantResponse, status_code=201)
def create_variant(
    payload: VariantCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvVariant:
    label = payload.label.strip()
    if not label:
        raise HTTPException(status_code=422, detail="Name this CV variant.")
    if not any(getattr(payload, field).strip() for field in CV_FIELDS):
        raise HTTPException(status_code=400, detail="Add some CV content before saving a variant.")

    job_description = payload.job_description.strip()
    job_title = payload.job_title.strip()
    company = payload.company.strip()
    job_id = payload.job_id
    if job_id is not None:
        job = (
            db.query(JobListing)
            .filter(JobListing.id == job_id, JobListing.user_id == user_id)
            .one_or_none()
        )
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        job_description = job_description or (job.description or "")
        job_title = job_title or job.title
        company = company or job.company

    variant = CvVariant(
        user_id=user_id,
        label=label,
        job_title=job_title,
        company=company,
        job_id=job_id,
        job_description=job_description,
        is_default=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **{field: getattr(payload, field) for field in CV_FIELDS},
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.patch("/{variant_id}", response_model=VariantResponse)
def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvVariant:
    variant = _own_variant(db, user_id, variant_id)
    changes = payload.model_dump(exclude_unset=True)
    if "label" in changes:
        label = (changes["label"] or "").strip()
        if not label:
            raise HTTPException(status_code=422, detail="Name this CV variant.")
        variant.label = label
    if "job_title" in changes:
        variant.job_title = (changes["job_title"] or "").strip()
    if "company" in changes:
        variant.company = (changes["company"] or "").strip()
    variant.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(variant)
    return variant


@router.delete("/{variant_id}", status_code=204, response_model=None)
def delete_variant(
    variant_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    variant = _own_variant(db, user_id, variant_id)
    db.delete(variant)
    db.commit()
    return None


@router.post("/{variant_id}/duplicate", response_model=VariantResponse, status_code=201)
def duplicate_variant(
    variant_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvVariant:
    source = _own_variant(db, user_id, variant_id)
    copy = CvVariant(
        user_id=user_id,
        label=f"Copy of {source.label}"[:160],
        job_title=source.job_title,
        company=source.company,
        job_id=source.job_id,
        job_description=source.job_description,
        is_default=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **{field: getattr(source, field) or "" for field in CV_FIELDS},
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


@router.post("/{variant_id}/default", response_model=VariantResponse)
def make_default(
    variant_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CvVariant:
    variant = _own_variant(db, user_id, variant_id)
    _clear_default(db, user_id)
    variant.is_default = True
    variant.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/{variant_id}/export")
def export_variant(
    variant_id: int,
    format: str = Query(pattern="^(pdf|docx)$"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    variant = _own_variant(db, user_id, variant_id)
    if not any((getattr(variant, field) or "").strip() for field in CV_FIELDS):
        raise HTTPException(status_code=400, detail="Add some CV content before exporting.")
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", variant.label.strip()).strip("-") or "CareerPilot-CV"
    contact = _contact_for_user(db, user_id)
    if format == "pdf":
        content = build_pdf(variant, contact)
        media_type = "application/pdf"
        filename = f"{safe_name}.pdf"
    else:
        content = build_docx(variant, contact)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{safe_name}.docx"
    return StreamingResponse(
        BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{variant_id}/analyse", response_model=VariantAnalysis)
def analyse_variant(
    variant_id: int,
    payload: ScoreRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> VariantAnalysis:
    variant = _own_variant(db, user_id, variant_id)
    description = payload.job_description.strip() or (variant.job_description or "")
    master = db.query(CvDocument).filter(CvDocument.user_id == user_id).one_or_none()
    if master is None:
        master = SimpleNamespace(**{field: "" for field in CV_FIELDS})
    return VariantAnalysis(
        variant=analyse_cv(variant, description),
        original=analyse_cv(master, description),
    )
