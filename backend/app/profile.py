from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CareerProfile

router = APIRouter(prefix="/api/v1/profile", tags=["career profile"])


class ProfilePayload(BaseModel):
    full_name: str = Field(default="", max_length=160)
    email: str = Field(default="", max_length=320)
    headline: str = Field(default="", max_length=200)
    location: str = Field(default="New Zealand", max_length=200)
    summary: str = Field(default="", max_length=5000)
    skills: str = Field(default="", max_length=5000)


class ProfileResponse(ProfilePayload):
    model_config = ConfigDict(from_attributes=True)
    id: int


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)) -> CareerProfile:
    profile = db.get(CareerProfile, 1)
    if profile is None:
        profile = CareerProfile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.put("", response_model=ProfileResponse)
def save_profile(payload: ProfilePayload, db: Session = Depends(get_db)) -> CareerProfile:
    profile = db.get(CareerProfile, 1)
    if profile is None:
        profile = CareerProfile(id=1, **payload.model_dump())
        db.add(profile)
    else:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
