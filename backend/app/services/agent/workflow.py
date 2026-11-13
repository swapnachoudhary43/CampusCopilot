"""Backend functions the agent is allowed to call.

There is no general SQL or Python tool. Each function checks the logged-in user.
"""

from sqlalchemy.orm import Session

from app.models.entities import Complaint, Event, User
from app.services.complaints import ComplaintError, create_complaint
from app.services.events import EventError, register_for_event
from app.services.ml.predict import ModelNotReady, predict_category
from app.services.ml.priority import suggest_priority
from app.services.rag.pipeline import answer_question
from app.utils.time import ensure_aware, utcnow


class ToolError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def search_campus_documents(db: Session, user: User, arguments: dict, history: list[dict]) -> dict:
    question = arguments.get("question", "").strip()
    if len(question) < 2:
        raise ToolError("Tell me what you want to look up in the campus documents.")
    result = answer_question(db, question, history)
    return {"reply": result["answer"], "sources": result["sources"], "metadata": result}


def list_available_events(db: Session, user: User, arguments: dict, history: list[dict]) -> dict:
    now = utcnow()
    events = db.query(Event).order_by(Event.starts_at.asc()).all()
    upcoming = [event for event in events if ensure_aware(event.starts_at) > now]
    if not upcoming:
        return {"reply": "There are no upcoming events in the system.", "sources": [], "metadata": {"tool": "list_available_events"}}
    lines = ["Upcoming events:"]
    for event in upcoming[:8]:
        lines.append(
            f"- {event.title} at {event.venue} on {ensure_aware(event.starts_at).strftime('%d %b %Y %H:%M UTC')} "
            f"(capacity {event.capacity})."
        )
    lines.append("Say 'register me for' and the event name if you want a seat. I will ask you to confirm.")
    return {"reply": "\n".join(lines), "sources": [], "metadata": {"tool": "list_available_events", "count": len(upcoming)}}


def check_complaint_status(db: Session, user: User, arguments: dict, history: list[dict]) -> dict:
    complaint_id = arguments.get("complaint_id")
    query = db.query(Complaint).filter(Complaint.user_id == user.id)
    if complaint_id:
        complaint = query.filter(Complaint.id == complaint_id).first()
        if complaint is None:
            return {
                "reply": "I cannot find that complaint on your account.",
                "sources": [],
                "metadata": {"tool": "check_complaint_status"},
            }
        return {"reply": _format_complaint(complaint), "sources": [], "metadata": {"tool": "check_complaint_status"}}
    rows = query.order_by(Complaint.created_at.desc()).limit(5).all()
    if not rows:
        return {"reply": "You have not submitted any complaints yet.", "sources": [], "metadata": {"tool": "check_complaint_status"}}
    lines = ["Your recent complaints:"]
    for row in rows:
        lines.append(f"- #{row.id} {row.title} — {row.status.replace('_', ' ')}")
    return {"reply": "\n".join(lines), "sources": [], "metadata": {"tool": "check_complaint_status"}}


def submit_complaint(db: Session, user: User, arguments: dict, history: list[dict]) -> dict:
    try:
        complaint = create_complaint(
            db,
            user=user,
            title=arguments["title"],
            description=arguments["description"],
            location=arguments.get("location"),
            user_category=None,
        )
    except ComplaintError as exc:
        raise ToolError(exc.message) from exc
    predicted = complaint.predicted_category or "not available"
    confidence = (
        f" ({complaint.prediction_confidence:.0%} confidence)" if complaint.prediction_confidence is not None else ""
    )
    reply = (
        f"Complaint #{complaint.id} has been submitted. Status: {complaint.status}. "
        f"Predicted category: {predicted}{confidence}. "
        f"Suggested priority: {complaint.suggested_priority}. {complaint.priority_reason} "
        "This is a keyword rule, not a machine-learning priority model."
    )
    return {
        "reply": reply,
        "sources": [],
        "metadata": {"tool": "submit_complaint", "complaint_id": complaint.id, "status": complaint.status},
    }


def register_event_tool(db: Session, user: User, arguments: dict, history: list[dict]) -> dict:
    event = db.get(Event, arguments["event_id"])
    if event is None:
        raise ToolError("That event no longer exists.")
    try:
        register_for_event(db, user, event)
    except EventError as exc:
        raise ToolError(exc.message) from exc
    return {
        "reply": f"You are registered for {event.title} at {event.venue}.",
        "sources": [],
        "metadata": {"tool": "register_for_event", "event_id": event.id},
    }


TOOLS = {
    "search_campus_documents": search_campus_documents,
    "list_available_events": list_available_events,
    "check_complaint_status": check_complaint_status,
    "submit_complaint": submit_complaint,
    "register_for_event": register_event_tool,
}


def preview_complaint(arguments: dict) -> str:
    priority = suggest_priority(f"{arguments['title']}\n{arguments['description']}")
    try:
        prediction = predict_category(f"{arguments['title']}. {arguments['description']}")
        category_line = (
            f"Predicted category: {prediction['predicted_category']} "
            f"(confidence {prediction['confidence']}, model {prediction['model_name']})."
        )
    except ModelNotReady:
        category_line = "Predicted category: unavailable because the classifier file has not been trained yet."
    location = arguments.get("location") or "not specified"
    return (
        "Please confirm this complaint before I save it.\n"
        f"Title: {arguments['title']}\n"
        f"Details: {arguments['description']}\n"
        f"Location: {location}\n"
        f"{category_line}\n"
        f"Suggested priority: {priority['suggested_priority']} — {priority['priority_reason']} "
        "This priority is a keyword rule, not an ML model.\n"
        "Reply YES to submit or NO to cancel."
    )


def _format_complaint(complaint: Complaint) -> str:
    return (
        f"Complaint #{complaint.id}: {complaint.title}\n"
        f"Status: {complaint.status.replace('_', ' ')}\n"
        f"Predicted category: {complaint.predicted_category or 'not stored'}\n"
        f"Suggested priority: {complaint.suggested_priority} (rule-based)"
    )
