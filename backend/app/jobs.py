from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CareerProfile, CvDocument, JobListing\nfrom app.job_matching import analyse_job_match

router = APIRouter(prefix="/api/v1/jobs", tags=["job discovery"])


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="New Zealand", max_length=200)
    description: str = Field(default="", max_length=20000)
    url: str = Field(default="", max_length=2000)
    source: str = Field(default="Manually added", max_length=120)


class JobUpdate(BaseModel):
    status: Literal["saved", "archived"]


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    status: str
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[JobResponse])
def list_jobs(
    q: str = Query(default="", max_length=200),
    location: str = Query(default="", max_length=200),
    status: Literal["all", "saved", "archived"] = "all",
    db: Session = Depends(get_db),
):
    query = db.query(JobListing)
    if status != "all":
        query = query.filter(JobListing.status == status)
    if location.strip():
        query = query.filter(JobListing.location.ilike(f"%{location.strip()}%"))
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(
            JobListing.title.ilike(term),
            JobListing.company.ilike(term),
            JobListing.location.ilike(term),
            JobListing.description.ilike(term),
            JobListing.source.ilike(term),
        ))
    return query.order_by(JobListing.created_at.desc(), JobListing.id.desc()).all()


@router.post("", response_model=JobResponse, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Add a job title.")
    url = payload.url.strip()
    if url:
        existing = db.query(JobListing).filter(JobListing.url == url).first()
        if existing:
            raise HTTPException(status_code=409, detail="This job URL is already in your saved jobs.")
    job = JobListing(
        title=title,
        company=payload.company.strip(),
        location=payload.location.strip() or "New Zealand",
        description=payload.description.strip(),
        url=url,
        source=payload.source.strip() or "Manually added",
        status="saved",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}/match")
def match_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobListing, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    profile = db.get(CareerProfile, 1)
    cv = db.get(CvDocument, 1)
    return analyse_job_match(job, profile, cv)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    job = db.get(JobListing, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.status = payload.status
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(JobListing, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    db.delete(job)
    db.commit()
    return None
