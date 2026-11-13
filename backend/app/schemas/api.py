"""Request and response shapes for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import (
    COMPLAINT_CATEGORIES,
    COMPLAINT_STATUSES,
    DOCUMENT_CATEGORIES,
    NOTICE_AUDIENCES,
    ROLES,
)


def _clean_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes. bcrypt ignores anything beyond that.")
    if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
        raise ValueError("Password must include at least one letter and one number.")
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    department: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return _clean_password(value)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(ORMModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    department: str | None
    is_active: bool
    is_demo: bool = False
    created_at: datetime

    @field_validator("is_demo", mode="before")
    @classmethod
    def demo_flag(cls, value):
        return bool(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department: str | None = Field(default=None, max_length=120)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        return _clean_password(value)


class AdminUserCreate(RegisterRequest):
    role: str

    @field_validator("role")
    @classmethod
    def role_ok(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError("Role must be student, faculty, or admin.")
        return value


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def role_ok(cls, value: str | None) -> str | None:
        if value is not None and value not in ROLES:
            raise ValueError("Role must be student, faculty, or admin.")
        return value


class DocumentPublic(ORMModel):
    id: int
    title: str
    category: str
    description: str | None
    original_filename: str
    status: str
    status_message: str | None
    page_count: int
    chunk_count: int
    source_url: str | None = None
    source_page_url: str | None = None
    publication_date: str | None = None
    retrieved_at: datetime | None = None
    provenance: str = "uploaded"
    document_type: str = "uploaded_pdf"
    department: str | None = None
    last_modified: str | None = None
    created_at: datetime


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=10, max_length=4000)
    location: str | None = Field(default=None, max_length=120)
    user_category: str | None = None

    @field_validator("user_category")
    @classmethod
    def category_ok(cls, value: str | None) -> str | None:
        if value is not None and value not in COMPLAINT_CATEGORIES:
            raise ValueError("Unknown complaint category.")
        return value


class ComplaintUpdate(BaseModel):
    status: str | None = None
    department: str | None = Field(default=None, max_length=120)
    assigned_to: int | None = None
    resolution_remarks: str | None = Field(default=None, max_length=4000)

    @field_validator("status")
    @classmethod
    def status_ok(cls, value: str | None) -> str | None:
        if value is not None and value not in COMPLAINT_STATUSES:
            raise ValueError("Unknown complaint status.")
        return value


class HistoryPublic(ORMModel):
    id: int
    action: str
    from_status: str | None
    to_status: str | None
    note: str | None
    actor_id: int | None
    created_at: datetime


class ComplaintPublic(ORMModel):
    id: int
    user_id: int
    title: str
    description: str
    location: str | None
    user_category: str | None
    predicted_category: str | None
    prediction_confidence: float | None
    prediction_model: str | None
    suggested_priority: str
    priority_method: str
    priority_reason: str | None
    priority_disclaimer: str = (
        "This priority is a transparent keyword rule, not a trained machine-learning model. "
        "An administrator should confirm it."
    )
    status: str
    department: str | None
    assigned_to: int | None
    assignee_name: str | None = None
    author_name: str | None = None
    resolution_remarks: str | None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("is_demo", mode="before")
    @classmethod
    def demo_flag(cls, value):
        return bool(value)
    history: list[HistoryPublic] = []


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    venue: str = Field(min_length=2, max_length=160)
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(ge=1, le=5000)


class EventPublic(ORMModel):
    id: int
    title: str
    description: str
    venue: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    is_demo: bool = False
    registered_count: int = 0
    viewer_registered: bool = False
    created_at: datetime


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=20000)
    audience: str = "all"
    source_url: str | None = Field(default=None, max_length=500)

    @field_validator("audience")
    @classmethod
    def audience_ok(cls, value: str) -> str:
        if value not in NOTICE_AUDIENCES:
            raise ValueError("Audience must be all, students, faculty, or hostel.")
        return value


class NoticePublic(ORMModel):
    id: int
    title: str
    body: str
    audience: str
    summary: str | None
    summary_method: str | None
    detected_audience: str | None
    deadlines: list[dict] = []
    action_items: list[str] = []
    extraction_disclaimer: str | None
    source_url: str | None = None
    provenance: str = "admin"
    created_at: datetime


class ChatRequest(BaseModel):
    content: str = Field(min_length=2, max_length=2000)


class ConversationPublic(ORMModel):
    id: int
    kind: str
    title: str
    created_at: datetime


class MessagePublic(BaseModel):
    id: int
    role: str
    content: str
    sources: list[dict] = []
    metadata: dict = {}
    created_at: datetime


class PredictRequest(BaseModel):
    text: str = Field(min_length=5, max_length=4000)


class DocumentCategory(BaseModel):
    category: str = "Other"

    @field_validator("category")
    @classmethod
    def category_ok(cls, value: str) -> str:
        if value not in DOCUMENT_CATEGORIES:
            raise ValueError("Unknown document category.")
        return value
