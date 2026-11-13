"""All relational tables for CampusCopilot.

The tables are kept together so the foreign keys can be read in one place
during a viva. Each class maps to one SQLite table.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.utils.time import utcnow


def _now() -> datetime:
    return utcnow()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('student', 'faculty', 'admin')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="author",
        foreign_keys="Complaint.user_id",
    )
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="Other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="processed", index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(160), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[str] = mapped_column(String(40), default="uploaded")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(40), default="uploaded_pdf")
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """One overlapping piece of a PDF page, plus its stored embedding.

    The embedding is kept in SQLite so the FAISS index can be rebuilt after
    a document is deleted without reading the PDF again.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(
            "status in ('submitted', 'assigned', 'in_progress', 'resolved', 'closed')",
            name="ck_complaints_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    predicted_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prediction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    suggested_priority: Mapped[str] = mapped_column(String(20), default="low")
    priority_method: Mapped[str] = mapped_column(String(40), default="rule_based")
    priority_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    resolution_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    author: Mapped[User] = relationship(back_populates="complaints", foreign_keys=[user_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    history: Mapped[list["ComplaintHistory"]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan"
    )


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    complaint: Mapped[Complaint] = relationship(back_populates="history")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column(String(160))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    registrations: Mapped[list["EventRegistration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    event: Mapped[Event] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship()


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20), default="all", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detected_audience: Mapped[str | None] = mapped_column(String(20), nullable=True)
    deadlines_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provenance: Mapped[str] = mapped_column(String(40), default="admin")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("kind in ('rag', 'agent')", name="ck_conversations_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(160), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    pending_actions: Mapped[list["PendingAction"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class PendingAction(Base):
    """A workflow waiting for missing details or for an explicit YES.

    Records are not created until status becomes completed.
    """

    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(60))
    arguments_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="pending_actions")


class OfficialSite(Base):
    """A verified official website. External links such as UGC are not stored here."""

    __tablename__ = "official_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(String(300), unique=True)
    category: Mapped[str] = mapped_column(String(40), default="university")
    parent: Mapped[str] = mapped_column(String(80), default="DAVV")
    status: Mapped[str] = mapped_column(String(40), default="discovered", index=True)
    pages_indexed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_crawled: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CrawlRecord(Base):
    """One fetch of an official URL. Failed and unchanged fetches stay visible to an admin."""

    __tablename__ = "crawl_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(700), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
