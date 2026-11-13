"""Controlled agent loop.

The model, when it is used at all, does not pick arbitrary code. This module
selects one whitelisted tool, asks for missing fields, and waits for YES
before it creates a complaint or an event registration.
"""

import json

from sqlalchemy.orm import Session

from app.models.entities import Conversation, Event, PendingAction, User
from app.services.agent.intent import (
    detect_intent,
    extract_complaint_fields,
    extract_complaint_id,
    extract_event_name,
    is_cancellation,
    is_confirmation,
)
from app.services.agent.workflow import TOOLS, ToolError, preview_complaint
from app.utils.time import ensure_aware, utcnow


def _open_pending(db: Session, conversation_id: int) -> PendingAction | None:
    return (
        db.query(PendingAction)
        .filter(
            PendingAction.conversation_id == conversation_id,
            PendingAction.status.in_(("collecting", "confirming")),
        )
        .order_by(PendingAction.id.desc())
        .first()
    )


def _save_messages(db: Session, conversation: Conversation, user_text: str, result: dict) -> dict:
    from app.models.entities import ChatMessage

    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=user_text))
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result["reply"],
            sources_json=json.dumps(result.get("sources") or []),
            metadata_json=json.dumps(result.get("metadata") or {}),
        )
    )
    if conversation.title == "New conversation":
        conversation.title = user_text[:80]
    db.commit()
    return result


def _finish(db, conversation, user_text, reply, sources=None, metadata=None, pending=False):
    result = {
        "reply": reply,
        "sources": sources or [],
        "metadata": metadata or {},
        "needs_confirmation": pending,
    }
    return _save_messages(db, conversation, user_text, result)


def _match_events(db: Session, name: str) -> list[Event]:
    now = utcnow()
    events = db.query(Event).order_by(Event.starts_at.asc()).all()
    upcoming = [event for event in events if ensure_aware(event.starts_at) > now]
    wanted = set(name.lower().split())
    matches = []
    for event in upcoming:
        title = event.title.lower()
        if name.lower() in title or title in name.lower():
            matches.append(event)
            continue
        title_tokens = set(title.split())
        overlap = wanted & title_tokens
        if wanted and len(overlap) / len(wanted) >= 0.6:
            matches.append(event)
    return matches


def _execute(db, user, pending: PendingAction, history: list[dict]) -> dict:
    if pending.tool_name not in TOOLS:
        raise ToolError("That action is not available.")
    arguments = json.loads(pending.arguments_json or "{}")
    result = TOOLS[pending.tool_name](db, user, arguments, history)
    pending.status = "completed"
    pending.updated_at = utcnow()
    db.commit()
    result["needs_confirmation"] = False
    return result


def handle_agent_turn(db: Session, user: User, conversation: Conversation, text: str, history: list[dict]) -> dict:
    cleaned = text.strip()
    pending = _open_pending(db, conversation.id)

    if pending and pending.status == "confirming":
        if is_confirmation(cleaned):
            try:
                result = _execute(db, user, pending, history)
            except ToolError as exc:
                pending.status = "cancelled"
                pending.updated_at = utcnow()
                db.commit()
                return _finish(db, conversation, cleaned, exc.message, metadata={"tool_error": True})
            return _save_messages(db, conversation, cleaned, result)
        if is_cancellation(cleaned):
            pending.status = "cancelled"
            pending.updated_at = utcnow()
            db.commit()
            return _finish(db, conversation, cleaned, "Cancelled. I did not change any records.")
        return _finish(
            db,
            conversation,
            cleaned,
            "A confirmation is still waiting. Reply YES to continue or NO to cancel.\n\n" + pending.summary,
            metadata={"needs_confirmation": True},
            pending=True,
        )

    if pending and pending.status == "collecting":
        if is_cancellation(cleaned):
            pending.status = "cancelled"
            pending.updated_at = utcnow()
            db.commit()
            return _finish(db, conversation, cleaned, "Cancelled. I did not change any records.")
        arguments = json.loads(pending.arguments_json or "{}")
        if pending.tool_name == "submit_complaint":
            arguments["description"] = cleaned
            arguments["title"] = cleaned[:80].rstrip(" .") or "Campus complaint"
            if len(arguments["description"]) < 10:
                return _finish(db, conversation, cleaned, "Please describe the problem in a little more detail.")
            pending.arguments_json = json.dumps(arguments)
            pending.summary = preview_complaint(arguments)
            pending.status = "confirming"
            pending.updated_at = utcnow()
            db.commit()
            return _finish(db, conversation, cleaned, pending.summary, pending=True, metadata={"needs_confirmation": True})
        if pending.tool_name == "register_for_event":
            matches = _match_events(db, cleaned)
            if len(matches) != 1:
                names = ", ".join(event.title for event in matches) or "none"
                return _finish(
                    db,
                    conversation,
                    cleaned,
                    f"I could not match that to exactly one upcoming event (matches: {names}). Please send the event name again.",
                )
            arguments = {"event_id": matches[0].id, "event_title": matches[0].title}
            pending.arguments_json = json.dumps(arguments)
            pending.summary = (
                f"Register you for {matches[0].title} at {matches[0].venue}? Reply YES to confirm or NO to cancel."
            )
            pending.status = "confirming"
            pending.updated_at = utcnow()
            db.commit()
            return _finish(db, conversation, cleaned, pending.summary, pending=True, metadata={"needs_confirmation": True})

    intent = detect_intent(cleaned)
    if intent == "search_campus_documents":
        result = TOOLS["search_campus_documents"](db, user, {"question": cleaned}, history)
        result["needs_confirmation"] = False
        return _save_messages(db, conversation, cleaned, result)
    if intent == "list_available_events":
        result = TOOLS["list_available_events"](db, user, {}, history)
        result["needs_confirmation"] = False
        return _save_messages(db, conversation, cleaned, result)
    if intent == "check_complaint_status":
        result = TOOLS["check_complaint_status"](
            db, user, {"complaint_id": extract_complaint_id(cleaned)}, history
        )
        result["needs_confirmation"] = False
        return _save_messages(db, conversation, cleaned, result)
    if intent == "submit_complaint":
        fields = extract_complaint_fields(cleaned)
        if len(fields["description"]) < 10:
            pending_row = PendingAction(
                user_id=user.id,
                conversation_id=conversation.id,
                tool_name="submit_complaint",
                arguments_json=json.dumps(fields),
                status="collecting",
                summary="Waiting for a description.",
            )
            db.add(pending_row)
            db.commit()
            return _finish(db, conversation, cleaned, "What happened? Please describe the problem in one or two sentences.")
        summary = preview_complaint(fields)
        db.add(
            PendingAction(
                user_id=user.id,
                conversation_id=conversation.id,
                tool_name="submit_complaint",
                arguments_json=json.dumps(fields),
                status="confirming",
                summary=summary,
            )
        )
        db.commit()
        return _finish(db, conversation, cleaned, summary, pending=True, metadata={"needs_confirmation": True})
    if intent == "register_for_event":
        name = extract_event_name(cleaned)
        if not name:
            db.add(
                PendingAction(
                    user_id=user.id,
                    conversation_id=conversation.id,
                    tool_name="register_for_event",
                    arguments_json="{}",
                    status="collecting",
                    summary="Waiting for an event name.",
                )
            )
            db.commit()
            listed = TOOLS["list_available_events"](db, user, {}, history)
            return _finish(
                db,
                conversation,
                cleaned,
                listed["reply"] + "\nWhich event should I register you for?",
            )
        matches = _match_events(db, name)
        if len(matches) != 1:
            listed = TOOLS["list_available_events"](db, user, {}, history)
            return _finish(
                db,
                conversation,
                cleaned,
                "I could not match that name to exactly one upcoming event, so I did not register you.\n\n" + listed["reply"],
            )
        event = matches[0]
        summary = f"Register you for {event.title} at {event.venue}? Reply YES to confirm or NO to cancel."
        db.add(
            PendingAction(
                user_id=user.id,
                conversation_id=conversation.id,
                tool_name="register_for_event",
                arguments_json=json.dumps({"event_id": event.id, "event_title": event.title}),
                status="confirming",
                summary=summary,
            )
        )
        db.commit()
        return _finish(db, conversation, cleaned, summary, pending=True, metadata={"needs_confirmation": True})
    return _finish(db, conversation, cleaned, "I could not match that request to a campus action.")
