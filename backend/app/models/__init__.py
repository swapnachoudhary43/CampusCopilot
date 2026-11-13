"""Importing this package registers every table."""

from app.models.entities import (
    AuditLog,
    ChatMessage,
    Complaint,
    ComplaintHistory,
    Conversation,
    Document,
    DocumentChunk,
    Event,
    EventRegistration,
    Notice,
    PendingAction,
    User,
)

__all__ = [
    "AuditLog",
    "ChatMessage",
    "Complaint",
    "ComplaintHistory",
    "Conversation",
    "Document",
    "DocumentChunk",
    "Event",
    "EventRegistration",
    "Notice",
    "PendingAction",
    "User",
]
