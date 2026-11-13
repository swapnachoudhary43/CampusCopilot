"""Dashboard numbers computed from the database.

Question text is grouped for administrators. Complaint descriptions are not
copied into these aggregates.
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import (
    AuditLog,
    ChatMessage,
    Complaint,
    ComplaintHistory,
    Conversation,
    Document,
    Event,
    EventRegistration,
    Notice,
    User,
)
from app.utils.time import ensure_aware


def _bounded(query, column, start: datetime | None, end: datetime | None):
    if start is not None:
        query = query.filter(column >= ensure_aware(start))
    if end is not None:
        query = query.filter(column < ensure_aware(end) + timedelta(days=1))
    return query


def build_overview(db: Session, start: datetime | None, end: datetime | None) -> dict:
    users = db.query(User)
    complaints = _bounded(db.query(Complaint), Complaint.created_at, start, end)
    events = db.query(Event)
    registrations = _bounded(
        db.query(EventRegistration).filter(EventRegistration.status == "registered"),
        EventRegistration.created_at,
        start,
        end,
    )
    by_category = (
        _bounded(db.query(Complaint.predicted_category, func.count(Complaint.id)), Complaint.created_at, start, end)
        .group_by(Complaint.predicted_category)
        .all()
    )
    by_status = (
        _bounded(db.query(Complaint.status, func.count(Complaint.id)), Complaint.created_at, start, end)
        .group_by(Complaint.status)
        .all()
    )
    opened_by_day = (
        _bounded(db.query(func.date(Complaint.created_at), func.count(Complaint.id)), Complaint.created_at, start, end)
        .group_by(func.date(Complaint.created_at))
        .order_by(func.date(Complaint.created_at))
        .all()
    )
    resolved_by_day = (
        _bounded(
            db.query(func.date(ComplaintHistory.created_at), func.count(ComplaintHistory.id)).filter(
                ComplaintHistory.to_status == "resolved"
            ),
            ComplaintHistory.created_at,
            start,
            end,
        )
        .group_by(func.date(ComplaintHistory.created_at))
        .order_by(func.date(ComplaintHistory.created_at))
        .all()
    )
    event_counts = (
        db.query(Event.title, func.count(EventRegistration.id))
        .outerjoin(
            EventRegistration,
            (EventRegistration.event_id == Event.id) & (EventRegistration.status == "registered"),
        )
        .group_by(Event.id)
        .order_by(func.count(EventRegistration.id).desc())
        .all()
    )
    question_norm = func.lower(func.trim(ChatMessage.content))
    questions = (
        _bounded(
            db.query(question_norm, func.count(ChatMessage.id))
            .join(Conversation, Conversation.id == ChatMessage.conversation_id)
            .filter(Conversation.kind == "rag", ChatMessage.role == "user"),
            ChatMessage.created_at,
            start,
            end,
        )
        .group_by(question_norm)
        .order_by(func.count(ChatMessage.id).desc())
        .limit(8)
        .all()
    )
    role_rows = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    return {
        "total_users": users.count(),
        "users_by_role": [{"role": role, "count": count} for role, count in role_rows],
        "total_complaints": complaints.count(),
        "complaints_by_category": [
            {"category": category or "Unclassified", "count": count} for category, count in by_category
        ],
        "complaints_by_status": [{"status": status, "count": count} for status, count in by_status],
        "complaints_opened_by_day": [{"date": str(day), "count": count} for day, count in opened_by_day],
        "complaints_resolved_by_day": [{"date": str(day), "count": count} for day, count in resolved_by_day],
        "total_events": events.count(),
        "total_registrations": registrations.count(),
        "registrations_by_event": [{"event": title, "count": count} for title, count in event_counts],
        "frequent_questions": [{"question": question[:180], "count": count} for question, count in questions],
        "documents_processed": db.query(Document).filter(Document.status == "processed").count(),
        "documents_needs_ocr": db.query(Document).filter(Document.status == "needs_ocr").count(),
        "notices": db.query(Notice).count(),
        "definitions": {
            "total_users": "All accounts, not limited by the date range.",
            "complaints": "Complaints created inside the date range. Categories use the stored ML prediction.",
            "frequent_questions": "Exact question text from document chat, lower-cased. Complaint text is excluded.",
        },
    }


def recent_activity(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
