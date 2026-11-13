"""Turn database rows into API dictionaries."""

import json

from app.constants import PRIORITY_DISCLAIMER
from app.models.entities import Complaint, Notice
from app.schemas.api import ComplaintPublic, HistoryPublic, NoticePublic, UserPublic
from app.services.events import registered_count, viewer_is_registered


def user_out(user) -> dict:
    return UserPublic.model_validate(user).model_dump()


def complaint_out(complaint: Complaint, with_history: bool = False) -> dict:
    payload = ComplaintPublic.model_validate(complaint)
    payload.priority_disclaimer = PRIORITY_DISCLAIMER
    payload.author_name = complaint.author.full_name if complaint.author else None
    payload.assignee_name = complaint.assignee.full_name if complaint.assignee else None
    if with_history:
        ordered = sorted(complaint.history, key=lambda row: (row.created_at, row.id))
        payload.history = [HistoryPublic.model_validate(row) for row in ordered]
    else:
        payload.history = []
    return payload.model_dump()


def notice_out(notice: Notice) -> dict:
    payload = NoticePublic.model_validate(notice)
    payload.deadlines = json.loads(notice.deadlines_json or "[]")
    payload.action_items = json.loads(notice.action_items_json or "[]")
    return payload.model_dump()


def event_out(db, event, user) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "venue": event.venue,
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "capacity": event.capacity,
        "is_demo": bool(event.is_demo),
        "registered_count": registered_count(db, event.id),
        "viewer_registered": viewer_is_registered(db, event.id, user.id),
        "created_at": event.created_at,
    }
