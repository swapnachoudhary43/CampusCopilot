"""Complaint creation, visibility, and status changes."""

from sqlalchemy.orm import Session, joinedload

from app.constants import PRIORITY_DISCLAIMER, STATUS_TRANSITIONS
from app.models.entities import Complaint, ComplaintHistory, User
from app.services.audit import log_action
from app.services.ml.predict import ModelNotReady, predict_category
from app.services.ml.priority import suggest_priority
from app.utils.time import utcnow


class ComplaintError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def create_complaint(
    db: Session,
    *,
    user: User,
    title: str,
    description: str,
    location: str | None,
    user_category: str | None,
) -> Complaint:
    priority = suggest_priority(f"{title}\n{description}")
    predicted_category = None
    confidence = None
    model_name = None
    try:
        prediction = predict_category(f"{title}. {description}")
        predicted_category = prediction["predicted_category"]
        confidence = prediction["confidence"]
        model_name = prediction["model_name"]
    except ModelNotReady:
        predicted_category = None

    complaint = Complaint(
        user_id=user.id,
        title=title.strip(),
        description=description.strip(),
        location=location.strip() if location else None,
        user_category=user_category,
        predicted_category=predicted_category,
        prediction_confidence=confidence,
        prediction_model=model_name,
        suggested_priority=priority["suggested_priority"],
        priority_method=priority["priority_method"],
        priority_reason=priority["priority_reason"],
        status="submitted",
    )
    db.add(complaint)
    db.flush()
    db.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            actor_id=user.id,
            action="created",
            to_status="submitted",
            note="Complaint submitted.",
        )
    )
    log_action(
        db,
        user_id=user.id,
        action="complaint_created",
        entity_type="complaint",
        entity_id=str(complaint.id),
        details=title[:160],
    )
    db.commit()
    db.refresh(complaint)
    return complaint


def visible_complaints(db: Session, user: User):
    query = db.query(Complaint).options(joinedload(Complaint.author), joinedload(Complaint.assignee))
    if user.role == "student":
        query = query.filter(Complaint.user_id == user.id)
    elif user.role == "faculty":
        query = query.filter(Complaint.assigned_to == user.id)
    return query.order_by(Complaint.created_at.desc())


def get_visible_complaint(db: Session, user: User, complaint_id: int) -> Complaint:
    complaint = (
        visible_complaints(db, user)
        .filter(Complaint.id == complaint_id)
        .first()
    )
    if complaint is None:
        raise ComplaintError("That complaint is not available on your account.", 404)
    return complaint


def update_complaint(db: Session, actor: User, complaint: Complaint, changes: dict) -> Complaint:
    if actor.role == "student":
        raise ComplaintError("Students cannot change complaint status.", 403)
    if actor.role == "faculty" and complaint.assigned_to != actor.id:
        raise ComplaintError("You can update only complaints assigned to you.", 403)

    notes = []
    new_status = changes.get("status") or complaint.status
    if changes.get("assigned_to") is not None:
        assignee = db.get(User, changes["assigned_to"])
        if assignee is None or not assignee.is_active or assignee.role not in {"faculty", "admin"}:
            raise ComplaintError("Complaints can be assigned only to an active faculty or administrator account.", 400)
        complaint.assigned_to = assignee.id
        notes.append(f"Assigned to {assignee.full_name}.")
        if complaint.status == "submitted" and new_status == "submitted":
            new_status = "assigned"
    if "department" in changes and changes["department"] is not None:
        complaint.department = changes["department"]
        notes.append(f"Department set to {changes['department']}.")

    if new_status != complaint.status:
        allowed = STATUS_TRANSITIONS.get(complaint.status, set())
        if new_status not in allowed:
            raise ComplaintError(
                f"Cannot move a complaint from {complaint.status} to {new_status}.",
                400,
            )
        if new_status in {"resolved", "closed"}:
            remarks = changes.get("resolution_remarks") or complaint.resolution_remarks
            if not remarks or not remarks.strip():
                raise ComplaintError("Add resolution remarks before resolving or closing a complaint.", 400)
            complaint.resolution_remarks = remarks.strip()
        elif changes.get("resolution_remarks"):
            complaint.resolution_remarks = changes["resolution_remarks"].strip()
        previous = complaint.status
        complaint.status = new_status
        db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                actor_id=actor.id,
                action="status_change",
                from_status=previous,
                to_status=new_status,
                note=" ".join(notes) or None,
            )
        )
    elif notes or changes.get("resolution_remarks"):
        if changes.get("resolution_remarks"):
            complaint.resolution_remarks = changes["resolution_remarks"].strip()
        db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                actor_id=actor.id,
                action="assignment",
                from_status=complaint.status,
                to_status=complaint.status,
                note=" ".join(notes) or changes.get("resolution_remarks"),
            )
        )
    complaint.updated_at = utcnow()
    log_action(
        db,
        user_id=actor.id,
        action="complaint_updated",
        entity_type="complaint",
        entity_id=str(complaint.id),
        details=complaint.status,
    )
    db.commit()
    db.refresh(complaint)
    return complaint


def priority_fields() -> dict:
    return {"priority_disclaimer": PRIORITY_DISCLAIMER}
