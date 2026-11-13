"""Complaint submission and staff updates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.entities import User
from app.routes.serializers import complaint_out
from app.schemas.api import ComplaintCreate, ComplaintUpdate
from app.services.complaints import ComplaintError, create_complaint, get_visible_complaint, update_complaint, visible_complaints

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.get("")
def list_complaints(
    status: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = visible_complaints(db, user)
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(predicted_category=category)
    return [complaint_out(row) for row in query.all()]


@router.post("", status_code=201)
def submit_complaint(
    body: ComplaintCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    complaint = create_complaint(
        db,
        user=user,
        title=body.title,
        description=body.description,
        location=body.location,
        user_category=body.user_category,
    )
    complaint = get_visible_complaint(db, user, complaint.id)
    return complaint_out(complaint, with_history=True)


@router.get("/{complaint_id}")
def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        complaint = get_visible_complaint(db, user, complaint_id)
    except ComplaintError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return complaint_out(complaint, with_history=True)


@router.patch("/{complaint_id}")
def patch_complaint(
    complaint_id: int,
    body: ComplaintUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        complaint = get_visible_complaint(db, user, complaint_id)
        updated = update_complaint(db, user, complaint, body.model_dump(exclude_unset=True))
        updated = get_visible_complaint(db, user, updated.id)
    except ComplaintError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return complaint_out(updated, with_history=True)
