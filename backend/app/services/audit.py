"""Append-only records of important actions.

The caller commits the session. This function does not commit on its own,
so the audit row is saved in the same transaction as the change it describes.
"""

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def log_action(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )
