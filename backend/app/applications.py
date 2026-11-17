from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import JobApplication

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
Stage = Literal["interested", "preparing", "ready_to_apply", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]

class ApplicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)

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
    created_at: datetime
    updated_at: datetime

@router.get("", response_model=list[ApplicationResponse])
def list_applications(stage: Stage | None = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(JobApplication)
    if stage:
        query = query.filter(JobApplication.stage == stage)
    return query.order_by(JobApplication.updated_at.desc(), JobApplication.id.desc()).all()

@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Add a job title.")
    item = JobApplication(title=title, company=payload.company.strip(), location=payload.location.strip(), url=payload.url.strip(), stage="interested")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.patch("/{application_id}", response_model=ApplicationResponse)
def update_application(application_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)):
    item = db.get(JobApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in {"title", "company", "location", "url", "next_action", "notes"} and value is not None:
            value = value.strip()
        setattr(item, key, value)
    if item.stage == "applied" and item.applied_at is None:
        item.applied_at = date.today()
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    item = db.get(JobApplication, application_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    db.delete(item)
    db.commit()
    return None
