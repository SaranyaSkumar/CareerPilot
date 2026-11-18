"""Multiple, user-owned career profiles used as independent CV tailoring bases."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import CareerTrackProfile, CvDocument

router = APIRouter(prefix="/api/v1/career-profiles", tags=["Career profiles"])


class CareerProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    employment_type: str = Field(default="full_time", pattern="^(full_time|part_time|contract|casual|custom)$")
    target_roles: str = Field(default="", max_length=1000)
    location: str = Field(default="New Zealand", max_length=200)
    headline: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=5000)
    experience: str = Field(default="", max_length=20000)
    skills: str = Field(default="", max_length=8000)
    education: str = Field(default="", max_length=8000)


class CareerProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    employment_type: str | None = Field(default=None, pattern="^(full_time|part_time|contract|casual|custom)$")
    target_roles: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=5000)
    experience: str | None = Field(default=None, max_length=20000)
    skills: str | None = Field(default=None, max_length=8000)
    education: str | None = Field(default=None, max_length=8000)


class CareerProfileResponse(CareerProfilePayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


def _owned(db: Session, user_id: uuid.UUID, profile_id: int) -> CareerTrackProfile:
    row = db.query(CareerTrackProfile).filter(
        CareerTrackProfile.id == profile_id,
        CareerTrackProfile.user_id == user_id,
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Career profile not found.")
    return row


@router.get("", response_model=list[CareerProfileResponse])
def list_profiles(user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return db.query(CareerTrackProfile).filter(
        CareerTrackProfile.user_id == user_id
    ).order_by(CareerTrackProfile.updated_at.desc(), CareerTrackProfile.id.desc()).all()


@router.post("", response_model=CareerProfileResponse, status_code=201)
def create_profile(payload: CareerProfilePayload, user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    values = payload.model_dump()
    values["name"] = values["name"].strip()
    if not values["name"]:
        raise HTTPException(status_code=422, detail="Give this career profile a name.")
    row = CareerTrackProfile(user_id=user_id, **values)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{profile_id}", response_model=CareerProfileResponse)
def update_profile(profile_id: int, payload: CareerProfileUpdate, user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = _owned(db, user_id, profile_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "name":
            value = (value or "").strip()
            if not value:
                raise HTTPException(status_code=422, detail="Give this career profile a name.")
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{profile_id}", status_code=204, response_model=None)
def delete_profile(profile_id: int, user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = _owned(db, user_id, profile_id)
    db.delete(row)
    db.commit()
    return None


@router.post("/from-master/{profile_id}", response_model=CareerProfileResponse)
def refresh_from_master(profile_id: int, user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = _owned(db, user_id, profile_id)
    master = db.query(CvDocument).filter(CvDocument.user_id == user_id).one_or_none()
    if master is None:
        raise HTTPException(status_code=400, detail="Save your master CV before copying it into a profile.")
    for field in ("headline", "summary", "experience", "skills", "education"):
        setattr(row, field, getattr(master, field) or "")
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row
