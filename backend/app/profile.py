import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.models import CareerProfile
from app.ownership import get_or_create_for_user

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
def get_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CareerProfile:
    return get_or_create_for_user(db, CareerProfile, user_id)


@router.put("", response_model=ProfileResponse)
def save_profile(
    payload: ProfilePayload,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CareerProfile:
    profile = get_or_create_for_user(db, CareerProfile, user_id)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
