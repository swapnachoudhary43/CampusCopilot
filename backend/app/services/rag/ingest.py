"""PDF ingestion: extract, chunk, embed, and index."""

from uuid import uuid4

import pymupdf
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Document, DocumentChunk
from app.services.rag.chunking import chunk_pages
from app.services.rag.embeddings import get_embedder
from app.services.rag.vector_store import index_backend_name, rebuild_index

import numpy as np


class DocumentProcessError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_pages(file_path: str) -> list[tuple[int, str]]:
    try:
        pdf = pymupdf.open(file_path)
    except Exception as exc:
        raise DocumentProcessError("The file could not be read as a PDF. It may be corrupted.") from exc
    if pdf.page_count == 0:
        pdf.close()
        raise DocumentProcessError("The PDF has no pages.")
    if pdf.page_count > 80:
        count = pdf.page_count
        pdf.close()
        raise DocumentProcessError(f"The PDF has {count} pages. The maximum for this project is 80.")
    pages = []
    for index, page in enumerate(pdf):
        pages.append((index + 1, page.get_text("text") or ""))
    pdf.close()
    return pages


def rebuild_from_database(db: Session) -> int:
    embedder = get_embedder()
    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.status == "processed")
        .order_by(DocumentChunk.id.asc())
        .all()
    )
    if not chunks:
        return rebuild_index([], np.zeros((0, 1), dtype=np.float32), embedder.name)
    vectors = []
    ids = []
    for chunk in chunks:
        vector = np.frombuffer(chunk.embedding, dtype=np.float32).copy()
        vectors.append(vector)
        ids.append(chunk.id)
    matrix = np.vstack(vectors)
    return rebuild_index(ids, matrix, embedder.name)


def store_pdf(
    db: Session,
    *,
    owner_id: int,
    title: str,
    category: str,
    description: str | None,
    original_filename: str,
    payload: bytes,
    source_url: str | None = None,
    source_page_url: str | None = None,
    publication_date: str | None = None,
    retrieved_at=None,
    provenance: str = "uploaded",
) -> Document:
    settings = get_settings()
    if len(payload) > settings.max_upload_mb * 1024 * 1024:
        raise DocumentProcessError(f"The file is larger than {settings.max_upload_mb} MB.")
    if not original_filename.lower().endswith(".pdf"):
        raise DocumentProcessError("Only PDF files are allowed.")
    if not payload.startswith(b"%PDF"):
        raise DocumentProcessError("The file is not a valid PDF. Scanned images renamed to .pdf are also rejected here.")

    embedder = get_embedder()
    existing_backend = index_backend_name()
    if existing_backend and existing_backend != embedder.name:
        raise DocumentProcessError(
            "The search index was built with a different embedding backend. "
            "Use Rebuild search index after switching EMBEDDING_BACKEND, or delete the old index.",
            status_code=409,
        )

    stored_name = f"{uuid4().hex}.pdf"
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    path = settings.upload_path / stored_name
    path.write_bytes(payload)

    document = Document(
        title=title.strip(),
        category=category,
        description=description,
        original_filename=original_filename.split("/")[-1].split("\\")[-1][:255],
        stored_filename=stored_name,
        status="processing",
        uploaded_by=owner_id,
        source_url=source_url,
        source_page_url=source_page_url,
        publication_date=publication_date,
        retrieved_at=retrieved_at,
        provenance=provenance,
    )
    db.add(document)
    db.flush()

    try:
        pages = extract_pages(str(path))
    except DocumentProcessError:
        db.rollback()
        path.unlink(missing_ok=True)
        raise

    text_length = sum(len(text.strip()) for _, text in pages)
    if text_length < 40:
        document.status = "needs_ocr"
        document.status_message = (
            "Almost no text could be extracted. The PDF may be scanned. "
            "OCR is not implemented in this project, so the file was not indexed."
        )
        document.page_count = len(pages)
        document.chunk_count = 0
        db.commit()
        db.refresh(document)
        return document

    chunks = chunk_pages(pages, size=settings.chunk_size, overlap=settings.chunk_overlap)
    if not chunks:
        document.status = "needs_ocr"
        document.status_message = "No indexable text was found. OCR is not implemented."
        document.page_count = len(pages)
        db.commit()
        db.refresh(document)
        return document

    vectors = embedder.embed([chunk.text for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        db.add(
            DocumentChunk(
                document_id=document.id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding=np.asarray(vector, dtype=np.float32).tobytes(),
            )
        )
    document.page_count = len(pages)
    document.chunk_count = len(chunks)
    document.status = "processed"
    document.status_message = "Text extracted and indexed."
    db.commit()
    rebuild_from_database(db)
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    path = get_settings().upload_path / document.stored_filename
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
    rebuild_from_database(db)


def reembed_all(db: Session) -> int:
    """Create fresh vectors with the current embedding backend and rebuild FAISS."""
    embedder = get_embedder()
    chunks = db.query(DocumentChunk).order_by(DocumentChunk.id.asc()).all()
    if not chunks:
        rebuild_index([], np.zeros((0, 1), dtype=np.float32), embedder.name)
        return 0
    vectors = embedder.embed([chunk.text for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = np.asarray(vector, dtype=np.float32).tobytes()
    db.commit()
    return rebuild_from_database(db)
