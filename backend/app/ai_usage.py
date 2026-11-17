"""Reserve, complete, and release Anthropic spend for the CV-writing caps."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai_pricing import (
    REQUEST_CAP_USD,
    daily_user_cap_usd,
    estimate_cost_usd,
    format_usd,
    monthly_cap_usd,
)
from app.ai_pricing import CapMisconfigured
from app.models import AiUsageEvent

logger = logging.getLogger("careerpilot.ai")

USAGE_NOT_READY = "AI usage tracking is not ready. Apply the ai_usage_events migration."
CAP_MISCONFIGURED = "AI spending limits are not configured correctly."


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def start_of_utc_day(now: datetime | None = None) -> datetime:
    current = _as_utc(now or datetime.now(timezone.utc))
    return current.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_utc_month(now: datetime | None = None) -> datetime:
    current = _as_utc(now or datetime.now(timezone.utc))
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _amount(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def spend_since(
    db: Session,
    *,
    start: datetime,
    user_id: uuid.UUID | None = None,
) -> Decimal:
    """Sum reserved estimates and completed actuals since `start`.

    Released rows are ignored. A reserved row counts its pre-call estimate so
    two overlapping requests cannot both slip under the cap.
    """

    try:
        query = db.query(AiUsageEvent).filter(AiUsageEvent.status.in_(("reserved", "completed")))
        if user_id is not None:
            query = query.filter(AiUsageEvent.user_id == user_id)
        rows = query.all()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=USAGE_NOT_READY) from exc

    total = Decimal("0")
    for row in rows:
        if _as_utc(row.created_at) < start:
            continue
        if row.status == "completed" and row.actual_cost_usd is not None:
            total += _amount(row.actual_cost_usd)
        else:
            total += _amount(row.estimated_cost_usd)
    return total


def usage_snapshot(db: Session, user_id: uuid.UUID) -> dict[str, str]:
    try:
        daily_cap = daily_user_cap_usd()
        monthly_cap = monthly_cap_usd()
    except CapMisconfigured as exc:
        raise HTTPException(status_code=503, detail=CAP_MISCONFIGURED) from exc
    return {
        "daily_cap_usd": format_usd(daily_cap),
        "daily_spent_usd": format_usd(spend_since(db, start=start_of_utc_day(), user_id=user_id)),
        "monthly_cap_usd": format_usd(monthly_cap),
        "monthly_spent_usd": format_usd(spend_since(db, start=start_of_utc_month())),
    }


def refuse_if_request_too_expensive(
    *,
    operation: str,
    model: str,
    user_id: uuid.UUID,
    input_tokens: int,
    max_tokens: int,
) -> Decimal:
    estimated = estimate_cost_usd(model, input_tokens, max_tokens)
    if estimated > REQUEST_CAP_USD:
        logger.info(
            "ai_request_refused provider=anthropic operation=%s model=%s user=%s "
            "estimated_input_tokens=%s max_tokens=%s estimated_usd=%s reason=request_cap",
            operation,
            model,
            user_id,
            input_tokens,
            max_tokens,
            format_usd(estimated),
        )
        raise HTTPException(
            status_code=429,
            detail="This request would exceed the US$0.50 limit.",
        )
    return estimated


def reserve_usage(
    db: Session,
    *,
    user_id: uuid.UUID,
    operation: str,
    model: str,
    input_tokens: int,
    max_tokens: int,
    estimated_cost: Decimal,
) -> AiUsageEvent:
    try:
        daily_cap = daily_user_cap_usd()
        monthly_cap = monthly_cap_usd()
    except CapMisconfigured as exc:
        raise HTTPException(status_code=503, detail=CAP_MISCONFIGURED) from exc

    daily = spend_since(db, start=start_of_utc_day(), user_id=user_id)
    if daily + estimated_cost > daily_cap:
        logger.info(
            "ai_request_refused provider=anthropic operation=%s model=%s user=%s "
            "estimated_input_tokens=%s max_tokens=%s estimated_usd=%s reason=daily_cap",
            operation,
            model,
            user_id,
            input_tokens,
            max_tokens,
            format_usd(estimated_cost),
        )
        raise HTTPException(
            status_code=429,
            detail=f"You have reached the daily AI limit of US${format_usd(daily_cap)}.",
        )

    monthly = spend_since(db, start=start_of_utc_month())
    if monthly + estimated_cost > monthly_cap:
        logger.info(
            "ai_request_refused provider=anthropic operation=%s model=%s user=%s "
            "estimated_input_tokens=%s max_tokens=%s estimated_usd=%s reason=monthly_cap",
            operation,
            model,
            user_id,
            input_tokens,
            max_tokens,
            format_usd(estimated_cost),
        )
        raise HTTPException(status_code=429, detail="The workspace has reached its monthly AI limit.")

    row = AiUsageEvent(
        user_id=user_id,
        operation=operation,
        model=model,
        status="reserved",
        input_tokens=input_tokens,
        output_tokens=max_tokens,
        estimated_cost_usd=estimated_cost,
        created_at=datetime.now(timezone.utc),
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=USAGE_NOT_READY) from exc
    return row


def complete_usage(
    db: Session,
    row: AiUsageEvent,
    *,
    input_tokens: int,
    output_tokens: int,
    actual_cost: Decimal,
) -> None:
    row.status = "completed"
    row.input_tokens = input_tokens
    row.output_tokens = output_tokens
    row.actual_cost_usd = actual_cost
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=USAGE_NOT_READY) from exc
    logger.info(
        "ai_request_completed provider=anthropic operation=%s model=%s user=%s "
        "input_tokens=%s output_tokens=%s estimated_usd=%s actual_usd=%s",
        row.operation,
        row.model,
        row.user_id,
        input_tokens,
        output_tokens,
        format_usd(_amount(row.estimated_cost_usd)),
        format_usd(actual_cost),
    )


def release_usage(db: Session, row: AiUsageEvent) -> None:
    row.status = "released"
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
