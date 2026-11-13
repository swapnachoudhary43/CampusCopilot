"""Upload, list, and delete institutional PDFs."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.constants import DOCUMENT_CATEGORIES
from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.entities import Document, User
from app.schemas.api import DocumentPublic
from app.services.audit import log_action
from app.services.rag.ingest import DocumentProcessError, delete_document, reembed_all, store_pdf
from app.services.rag.vector_store import indexed_count

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _out(document: Document) -> dict:
    return DocumentPublic.model_validate(document).model_dump()


@router.get("")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Document).order_by(Document.created_at.desc())
    return [_out(document) for document in query.all()]


@router.get("/index-status")
def index_status(user: User = Depends(get_current_user)):
    return {"indexed_chunks": indexed_count()}


@router.post("", status_code=201)
async def upload_document(
    title: str = Form(...),
    category: str = Form("Other"),
    description: str | None = Form(None),
    source_url: str | None = Form(None),
    publication_date: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown document category.")
    if not title.strip():
        raise HTTPException(status_code=400, detail="A document title is required.")
    payload = await file.read()
    try:
        document = store_pdf(
            db,
            owner_id=actor.id,
            title=title,
            category=category,
            description=description,
            original_filename=file.filename or "upload.pdf",
            payload=payload,
            source_url=(source_url or "").strip() or None,
            publication_date=(publication_date or "").strip() or None,
            provenance="uploaded",
        )
    except DocumentProcessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    log_action(
        db,
        user_id=actor.id,
        action="document_uploaded",
        entity_type="document",
        entity_id=str(document.id),
        details=f"{document.status}: {document.title}",
    )
    db.commit()
    return _out(document)


@router.delete("/{document_id}")
def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    title = document.title
    delete_document(db, document)
    log_action(
        db,
        user_id=actor.id,
        action="document_deleted",
        entity_type="document",
        entity_id=str(document_id),
        details=title,
    )
    db.commit()
    return {"detail": "Document deleted and the search index was rebuilt."}


@router.post("/reindex")
def reindex(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    try:
        count = reembed_all(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_action(db, user_id=actor.id, action="index_rebuilt", entity_type="document", details=str(count))
    db.commit()
    return {"indexed_chunks": count}
