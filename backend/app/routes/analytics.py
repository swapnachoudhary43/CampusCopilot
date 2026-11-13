"""Admin analytics computed from stored records."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.session import get_db
from app.models.entities import User
from app.services.analytics.metrics import build_overview, recent_activity

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _as_utc(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


@router.get("/overview")
def overview(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    start = _as_utc(from_date)
    end = _as_utc(to_date)
    if start and end and end < start:
        raise HTTPException(status_code=400, detail="The end date must be on or after the start date.")
    return build_overview(db, start, end)


@router.get("/activity")
def activity(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    return recent_activity(db)
