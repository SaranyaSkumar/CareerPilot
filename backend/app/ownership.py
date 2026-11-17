"""Load the signed-in user's own rows.

Profile and CV drafts are one row per user, created the first time that user
reads or saves them. A concurrent first request can lose the unique-user_id
race; the loser reads the row the winner inserted.
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


def get_or_create_for_user(db: Session, model: type[ModelT], user_id: uuid.UUID) -> ModelT:
    row = db.query(model).filter(model.user_id == user_id).one_or_none()
    if row is not None:
        return row
    row = model(user_id=user_id)
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        existing = db.query(model).filter(model.user_id == user_id).one_or_none()
        if existing is None:
            raise
        return existing
