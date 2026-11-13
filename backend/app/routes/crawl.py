"""Administrator controls for the official-website crawl."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database.session import get_db, get_session_factory
from app.models.entities import CrawlRecord, OfficialSite, User
from app.services.crawl.runner import crawl_status, start_crawl_background

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


class CrawlStart(BaseModel):
    max_pages: int = Field(default=70, ge=1, le=120)
    max_pdfs: int = Field(default=6, ge=0, le=20)


def _row(record: CrawlRecord) -> dict:
    return {
        "url": record.url,
        "status": record.status,
        "title": record.title,
        "document_id": record.document_id,
        "error": record.error,
        "http_status": record.http_status,
        "fetched_at": record.fetched_at.isoformat() if record.fetched_at else None,
    }


@router.post("/start")
def start_crawl(body: CrawlStart, actor: User = Depends(require_roles("admin"))):
    started = start_crawl_background(
        get_session_factory,
        max_pages=body.max_pages,
        max_pdfs=body.max_pdfs,
        owner_id=actor.id,
    )
    if not started:
        raise HTTPException(status_code=409, detail={"detail": "A crawl is already running.", "code": "crawl_running"})
    return {"started": True, "status": crawl_status()}


@router.post("/retry")
def retry_failed(actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    urls = [
        record.url
        for record in db.query(CrawlRecord).filter(CrawlRecord.status.in_(("failed", "needs_render"))).all()
    ]
    if not urls:
        return {"started": False, "reason": "No failed pages are waiting."}
    started = start_crawl_background(get_session_factory, max_pages=len(urls), max_pdfs=len(urls), owner_id=actor.id, seeds=urls)
    if not started:
        raise HTTPException(status_code=409, detail={"detail": "A crawl is already running.", "code": "crawl_running"})
    return {"started": True, "urls": len(urls)}


@router.get("")
def list_crawl(actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    records = db.query(CrawlRecord).order_by(CrawlRecord.fetched_at.desc()).limit(80).all()
    counts: dict[str, int] = {}
    for record in db.query(CrawlRecord).all():
        counts[record.status] = counts.get(record.status, 0) + 1
    sites = [
        {
            "name": site.name,
            "url": site.url,
            "category": site.category,
            "parent": site.parent,
            "status": site.status,
            "pages_indexed": site.pages_indexed,
            "error": site.error,
            "last_crawled": site.last_crawled.isoformat() if site.last_crawled else None,
        }
        for site in db.query(OfficialSite).order_by(OfficialSite.name.asc()).all()
    ]
    return {"run": crawl_status(), "counts": counts, "records": [_row(record) for record in records], "sites": sites}
