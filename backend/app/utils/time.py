"""Timezone-aware timestamps. Stored values are UTC."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    """SQLite often returns naive datetimes. Treat those as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
