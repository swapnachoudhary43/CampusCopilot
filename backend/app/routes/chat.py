"""Document question answering."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.entities import ChatMessage, Conversation, User
from app.schemas.api import ChatRequest, ConversationPublic
from app.services.rag.pipeline import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _owned(db: Session, user: User, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.kind != "rag":
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


def _message_out(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "sources": json.loads(message.sources_json or "[]"),
        "metadata": json.loads(message.metadata_json or "{}"),
        "created_at": message.created_at,
    }


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id, Conversation.kind == "rag")
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [ConversationPublic.model_validate(row).model_dump() for row in rows]


@router.post("/sessions", status_code=201)
def create_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conversation = Conversation(user_id=user.id, kind="rag", title="New conversation")
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
def ask(
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
    result = answer_question(db, body.content.strip(), history)
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=body.content.strip()))
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result["answer"],
            sources_json=json.dumps(result["sources"]),
            metadata_json=json.dumps(
                {
                    "answer_mode": result["answer_mode"],
                    "similarity_threshold": result["similarity_threshold"],
                    "embedding_backend": result["embedding_backend"],
                }
            ),
        )
    )
    if conversation.title == "New conversation":
        conversation.title = body.content.strip()[:80]
    db.commit()
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.id.desc())
        .limit(1)
        .all()
    )
    return _message_out(messages[0])


@router.delete("/sessions/{conversation_id}")
def delete_session(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = _owned(db, user, conversation_id)
    db.delete(conversation)
    db.commit()
    return {"detail": "Conversation deleted."}
