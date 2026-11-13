"""Campus events and registrations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.entities import Event, EventRegistration, User
from app.routes.serializers import event_out
from app.schemas.api import EventCreate
from app.services.audit import log_action
from app.services.events import EventError, cancel_registration, register_for_event, validate_window

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    events = db.query(Event).order_by(Event.starts_at.asc()).all()
    return [event_out(db, event, user) for event in events]


@router.post("", status_code=201)
def create_event(
    body: EventCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    try:
        validate_window(body.starts_at, body.ends_at)
    except EventError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    event = Event(
        title=body.title.strip(),
        description=body.description.strip(),
        venue=body.venue.strip(),
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        capacity=body.capacity,
        created_by=actor.id,
    )
    db.add(event)
    db.flush()
    log_action(db, user_id=actor.id, action="event_created", entity_type="event", entity_id=str(event.id), details=event.title)
    db.commit()
    db.refresh(event)
    return event_out(db, event, actor)


@router.put("/{event_id}")
def update_event(
    event_id: int,
    body: EventCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        validate_window(body.starts_at, body.ends_at)
    except EventError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    event.title = body.title.strip()
    event.description = body.description.strip()
    event.venue = body.venue.strip()
    event.starts_at = body.starts_at
    event.ends_at = body.ends_at
    event.capacity = body.capacity
    log_action(db, user_id=actor.id, action="event_updated", entity_type="event", entity_id=str(event.id), details=event.title)
    db.commit()
    db.refresh(event)
    return event_out(db, event, actor)


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    title = event.title
    db.delete(event)
    log_action(db, user_id=actor.id, action="event_deleted", entity_type="event", entity_id=str(event_id), details=title)
    db.commit()
    return {"detail": "Event deleted."}


@router.post("/{event_id}/register")
def register(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        register_for_event(db, user, event)
    except EventError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return event_out(db, event, user)


@router.post("/{event_id}/cancel")
def cancel(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    try:
        cancel_registration(db, user, event)
    except EventError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return event_out(db, event, user)


@router.get("/me/registrations")
def my_registrations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(EventRegistration)
        .filter(EventRegistration.user_id == user.id, EventRegistration.status == "registered")
        .all()
    )
    events = []
    for row in rows:
        event = db.get(Event, row.event_id)
        if event is not None:
            events.append(event_out(db, event, user))
    events.sort(key=lambda item: item["starts_at"])
    return events
