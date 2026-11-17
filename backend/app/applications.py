import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import CvVersion, JobApplication

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
Stage = Literal["interested", "preparing", "ready_to_apply", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]


class ApplicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="New Zealand", max_length=200)
    url: str = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Add a job title.")
        return value


class ApplicationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    stage: Stage | None = None
    applied_at: date | None = None
    next_action: str | None = Field(default=None, max_length=500)
    next_action_date: date | None = None
    notes: str | None = Field(default=None, max_length=10000)
    cv_version_id: int | None = None
    cover_letter: str = Field(default="", max_length=20000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Add a job title.")
        return value


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    location: str
    url: str
    stage: str
    applied_at: date | None
    next_action: str
    next_action_date: date | None
    notes: str
    cv_version_id: int | None
    cover_letter: str
    created_at: datetime
    updated_at: datetime


def _owned_application(db: Session, user_id: uuid.UUID, application_id: int) -> JobApplication:
    item = (
        db.query(JobApplication)
        .filter(JobApplication.id == application_id, JobApplication.user_id == user_id)
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return item


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    stage: Stage | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(JobApplication).filter(JobApplication.user_id == user_id)
    if stage:
        query = query.filter(JobApplication.stage == stage)
    return query.order_by(JobApplication.updated_at.desc(), JobApplication.id.desc()).all()


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(
    payload: ApplicationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = JobApplication(
        user_id=user_id,
        title=payload.title,
        company=payload.company.strip(),
        location=payload.location.strip() or "New Zealand",
        url=payload.url.strip(),
        stage="interested",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = _owned_application(db, user_id, application_id)
    changes = payload.model_dump(exclude_unset=True)
    if "cv_version_id" in changes and changes["cv_version_id"] is not None:
        version = (
            db.query(CvVersion)
            .filter(CvVersion.id == changes["cv_version_id"], CvVersion.user_id == user_id)
            .one_or_none()
        )
        if version is None:
            raise HTTPException(status_code=404, detail="CV version not found.")
    for key, value in changes.items():
        if key in {"company", "location", "url", "next_action", "notes", "cover_letter"} and value is not None:
            value = value.strip()
        setattr(item, key, value)
    if item.stage == "applied" and item.applied_at is None:
        item.applied_at = date.today()
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{application_id}", status_code=204)
def delete_application(
    application_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    item = _owned_application(db, user_id, application_id)
    db.delete(item)
    db.commit()
    return None
