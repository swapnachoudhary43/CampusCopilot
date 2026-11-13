"""Event creation and registration rules."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import Event, EventRegistration, User
from app.services.audit import log_action
from app.utils.time import ensure_aware, utcnow


class EventError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def registered_count(db: Session, event_id: int) -> int:
    return (
        db.query(EventRegistration)
        .filter(EventRegistration.event_id == event_id, EventRegistration.status == "registered")
        .count()
    )


def viewer_is_registered(db: Session, event_id: int, user_id: int) -> bool:
    row = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_id == event_id,
            EventRegistration.user_id == user_id,
            EventRegistration.status == "registered",
        )
        .first()
    )
    return row is not None


def validate_window(starts_at: datetime, ends_at: datetime) -> None:
    if ensure_aware(ends_at) <= ensure_aware(starts_at):
        raise EventError("The event end time must be after the start time.")


def register_for_event(db: Session, user: User, event: Event) -> EventRegistration:
    if ensure_aware(event.starts_at) <= utcnow():
        raise EventError("Registration is closed because this event has already started.")
    # The update takes SQLite's write lock before the capacity count, so two
    # requests cannot both pass a check against the old count.
    db.execute(text("UPDATE events SET capacity = capacity WHERE id = :event_id"), {"event_id": event.id})
    existing = (
        db.query(EventRegistration)
        .filter(EventRegistration.event_id == event.id, EventRegistration.user_id == user.id)
        .first()
    )
    if existing and existing.status == "registered":
        raise EventError("You are already registered for this event.", 409)
    if registered_count(db, event.id) >= event.capacity:
        raise EventError("This event is full.", 409)
    if existing:
        existing.status = "registered"
        existing.updated_at = utcnow()
        row = existing
    else:
        row = EventRegistration(event_id=event.id, user_id=user.id, status="registered")
        db.add(row)
    log_action(
        db,
        user_id=user.id,
        action="event_registered",
        entity_type="event",
        entity_id=str(event.id),
        details=event.title,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EventError("You are already registered for this event.", 409) from exc
    db.refresh(row)
    return row


def cancel_registration(db: Session, user: User, event: Event) -> EventRegistration:
    existing = (
        db.query(EventRegistration)
        .filter(
            EventRegistration.event_id == event.id,
            EventRegistration.user_id == user.id,
            EventRegistration.status == "registered",
        )
        .first()
    )
    if existing is None:
        raise EventError("You do not have an active registration for this event.", 404)
    existing.status = "cancelled"
    existing.updated_at = utcnow()
    log_action(
        db,
        user_id=user.id,
        action="event_registration_cancelled",
        entity_type="event",
        entity_id=str(event.id),
        details=event.title,
    )
    db.commit()
    db.refresh(existing)
    return existing
