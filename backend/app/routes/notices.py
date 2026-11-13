"""Notices and their extracted summaries."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.entities import Notice, User
from app.routes.serializers import notice_out
from app.schemas.api import NoticeCreate
from app.services.audit import log_action
from app.services.notices import dumps_result, summarise_notice

router = APIRouter(prefix="/api/notices", tags=["notices"])


def _save_summary(notice: Notice, body: str) -> None:
    result = summarise_notice(body)
    deadlines, actions = dumps_result(result)
    notice.summary = result["summary"]
    notice.summary_method = result["summary_method"]
    notice.detected_audience = result["detected_audience"]
    notice.deadlines_json = deadlines
    notice.action_items_json = actions
    notice.extraction_disclaimer = result["extraction_disclaimer"]


@router.get("")
def list_notices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    return [notice_out(notice) for notice in notices]


@router.get("/{notice_id}")
def get_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    return notice_out(notice)


@router.post("", status_code=201)
def create_notice(
    body: NoticeCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    notice = Notice(
        title=body.title.strip(),
        body=body.body.strip(),
        audience=body.audience,
        source_url=(body.source_url or "").strip() or None,
        provenance="admin",
        created_by=actor.id,
    )
    _save_summary(notice, notice.body)
    db.add(notice)
    db.flush()
    log_action(db, user_id=actor.id, action="notice_created", entity_type="notice", entity_id=str(notice.id), details=notice.title)
    db.commit()
    db.refresh(notice)
    return notice_out(notice)


@router.put("/{notice_id}")
def update_notice(
    notice_id: int,
    body: NoticeCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    notice.title = body.title.strip()
    notice.body = body.body.strip()
    notice.audience = body.audience
    notice.source_url = (body.source_url or "").strip() or None
    _save_summary(notice, notice.body)
    log_action(db, user_id=actor.id, action="notice_updated", entity_type="notice", entity_id=str(notice.id), details=notice.title)
    db.commit()
    db.refresh(notice)
    return notice_out(notice)


@router.delete("/{notice_id}")
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found.")
    title = notice.title
    db.delete(notice)
    log_action(db, user_id=actor.id, action="notice_deleted", entity_type="notice", entity_id=str(notice_id), details=title)
    db.commit()
    return {"detail": "Notice deleted."}
