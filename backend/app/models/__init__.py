"""Importing this package registers every table."""

from app.models.entities import (
    AuditLog,
    ChatMessage,
    Complaint,
    ComplaintHistory,
    Conversation,
    CrawlRecord,
    Document,
    DocumentChunk,
    Event,
    EventRegistration,
    Notice,
    OfficialSite,
    PendingAction,
    User,
)

__all__ = [
    "AuditLog",
    "ChatMessage",
    "Complaint",
    "ComplaintHistory",
    "Conversation",
    "CrawlRecord",
    "Document",
    "DocumentChunk",
    "Event",
    "EventRegistration",
    "Notice",
    "OfficialSite",
    "PendingAction",
    "User",
]
