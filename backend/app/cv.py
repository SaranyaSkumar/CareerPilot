from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CvDocument

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
