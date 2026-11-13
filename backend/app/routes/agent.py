"""Campus workflow assistant. Mutations wait for an explicit confirmation."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.entities import ChatMessage, Conversation, User
from app.schemas.api import ChatRequest, ConversationPublic
from app.services.agent.orchestrator import handle_agent_turn

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _owned(db: Session, user: User, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.kind != "agent":
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


def _message_out(message: ChatMessage) -> dict:
    metadata = json.loads(message.metadata_json or "{}")
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": json.loads(message.sources_json or "[]"),
        "metadata": metadata,
        "needs_confirmation": bool(metadata.get("needs_confirmation")),
        "created_at": message.created_at,
    }


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.kind == "agent")
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [ConversationPublic.model_validate(row).model_dump() for row in rows]


@router.post("/sessions", status_code=201)
def create_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conversation = Conversation(user_id=user.id, kind="agent", title="New conversation")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationPublic.model_validate(conversation).model_dump()


@router.get("/sessions/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _owned(db, user, conversation_id)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return [_message_out(message) for message in messages]


@router.post("/sessions/{conversation_id}/messages")
def act(
    conversation_id: int,
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _owned(db, user, conversation_id)
    previous = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    history = [{"role": message.role, "content": message.content} for message in previous]
    result = handle_agent_turn(db, user, conversation, body.content.strip(), history)
    latest = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id, ChatMessage.role == "assistant")
        .order_by(ChatMessage.id.desc())
        .first()
    )
    payload = _message_out(latest)
    payload["needs_confirmation"] = bool(result.get("needs_confirmation"))
    if payload["needs_confirmation"]:
        payload["metadata"]["needs_confirmation"] = True
    return payload
