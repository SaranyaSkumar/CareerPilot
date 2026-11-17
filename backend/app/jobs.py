import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.job_providers.types import canonical_url
from app.jobs_matching import analyse_job_fit
from app.models import CareerProfile, JobListing

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
    salary: str = ""
    posted_at: datetime | None = None
    status: str
    match_score: int | None = None
    created_at: datetime
    updated_at: datetime


class JobMatchResponse(BaseModel):
    job_id: int
    score: int | None
    skills_score: int | None
    role_score: int
    location_score: int
    matched_skills: list[str]
    not_found_skills: list[str]
    candidate_skills_mentioned: list[str]
    candidate_skills_not_mentioned: list[str]
    detected_requirement_count: int
    profile_ready: bool
    message: str


class JobDetailResponse(JobResponse):
    match: JobMatchResponse


def _own_job(db: Session, user_id: uuid.UUID, job_id: int) -> JobListing:
    job = (
        db.query(JobListing)
        .filter(JobListing.id == job_id, JobListing.user_id == user_id)
        .one_or_none()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _profile_for(db: Session, user_id: uuid.UUID) -> CareerProfile:
    profile = db.query(CareerProfile).filter(CareerProfile.user_id == user_id).one_or_none()
    return profile or CareerProfile(user_id=user_id)


def _serialize(job: JobListing, profile: CareerProfile) -> JobResponse:
    score = analyse_job_fit(job, profile)["score"]
    return JobResponse.model_validate(job).model_copy(update={"match_score": score})


def _sort_key(job: JobListing, score: int | None) -> tuple:
    posted = job.posted_at or job.created_at
    stamp = posted.timestamp() if posted is not None else 0
    return (score is None, -(score or 0), -stamp, -job.id)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    q: str = Query(default="", max_length=200),
    location: str = Query(default="", max_length=200),
    source: str = Query(default="", max_length=120),
    status: Literal["all", "saved", "archived", "discovered"] = "all",
    sort: Literal["recent", "match"] = "recent",
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    query = db.query(JobListing).filter(JobListing.user_id == user_id)
    if status != "all":
        query = query.filter(JobListing.status == status)
    if location.strip():
        query = query.filter(JobListing.location.ilike(f"%{location.strip()}%"))
    if source.strip():
        query = query.filter(func.lower(JobListing.source) == source.strip().lower())
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(
            JobListing.title.ilike(term),
            JobListing.company.ilike(term),
            JobListing.location.ilike(term),
            JobListing.description.ilike(term),
            JobListing.source.ilike(term),
        ))
    jobs = query.order_by(JobListing.created_at.desc(), JobListing.id.desc()).all()
    profile = _profile_for(db, user_id)
    if sort == "match":
        jobs = sorted(jobs, key=lambda job: _sort_key(job, analyse_job_fit(job, profile)["score"]))
    return [_serialize(job, profile) for job in jobs]


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    payload: JobCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Add a job title.")
    url = payload.url.strip()
    if url.lower().startswith(("http://", "https://")):
        url = canonical_url(url)
    if url:
        existing = (
            db.query(JobListing)
            .filter(JobListing.user_id == user_id, JobListing.url == url)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="This job URL is already in your saved jobs.")
    job = JobListing(
        user_id=user_id,
        title=title,
        company=payload.company.strip(),
        location=payload.location.strip() or "New Zealand",
        description=payload.description.strip(),
        url=url,
        source=payload.source.strip() or "Manually added",
        status="saved",
    )
    try:
        db.add(job)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This job URL is already in your saved jobs.") from None
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user_id, job_id)
    profile = _profile_for(db, user_id)
    fit = analyse_job_fit(job, profile)
    listing = _serialize(job, profile)
    return JobDetailResponse(**listing.model_dump(), match=JobMatchResponse.model_validate(fit))


@router.get("/{job_id}/match")
def match_job(
    job_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user_id, job_id)
    return analyse_job_fit(job, _profile_for(db, user_id))


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    payload: JobUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user_id, job_id)
    job.status = payload.status
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    job = _own_job(db, user_id, job_id)
    db.delete(job)
    db.commit()
    return None
