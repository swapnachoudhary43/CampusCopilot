"""Retrieval-augmented answering.

The route layer calls answer_question(). Embedding, search, and the language
model stay in this service so they can be tested without HTTP.
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import DocumentChunk
from app.services.rag.embeddings import get_embedder
from app.services.rag.generator import build_prompt, generate_with_gemini, quote_retrieved_passages
from app.services.rag.vector_store import search_index

INSUFFICIENT = (
    "The uploaded institutional documents do not contain enough information to answer this question. "
    "I will not guess a rule, date, or fee."
)


def _search_query(question: str, history: list[dict]) -> str:
    text = question.strip()
    lowered = text.lower()
    # A complete question such as "What is the canteen menu?" must be searched on its own.
    # Only glue on the previous question for an explicit follow-up or a short fragment.
    starts_follow = lowered.startswith(("and ", "what about", "how about", "then ", "also "))
    looks_complete = lowered.startswith(
        ("what ", "when ", "where ", "who ", "why ", "how ", "which ", "is ", "are ", "can ", "does ", "do ")
    )
    follow_up = starts_follow or (len(text) < 24 and not looks_complete)
    if not follow_up:
        return text
    previous = [item["content"] for item in history if item["role"] == "user"]
    if not previous:
        return text
    return f"{previous[-1]}\n{text}"


def retrieve(db: Session, query: str) -> list[dict]:
    settings = get_settings()
    embedder = get_embedder()
    vector = embedder.embed([query])[0]
    hits = search_index(vector, max(settings.retrieval_top_k * 2, settings.retrieval_top_k))
    # Several chunks of one page can all clear the cutoff. Keep them in reading
    # order and show the highest score, so the citation is not only the tail of the page.
    grouped: dict[tuple[int, int], list[tuple[float, DocumentChunk]]] = {}
    for chunk_id, score in hits:
        if score < settings.similarity_threshold:
            continue
        chunk = db.get(DocumentChunk, chunk_id)
        if chunk is None or chunk.document is None or chunk.document.status != "processed":
            continue
        key = (chunk.document_id, chunk.page_number)
        grouped.setdefault(key, []).append((float(score), chunk))
    sources = []
    for parts in grouped.values():
        parts.sort(key=lambda item: item[1].chunk_index)
        best = max(score for score, _chunk in parts)
        text = " ".join(chunk.text for _score, chunk in parts)
        first = parts[0][1]
        sources.append(
            {
                "document_id": first.document_id,
                "document_title": first.document.title,
                "page_number": first.page_number,
                "excerpt": text[:900],
                "score": round(best, 4),
            }
        )
    sources.sort(key=lambda item: item["score"], reverse=True)
    return sources[: settings.retrieval_top_k]


def answer_question(db: Session, question: str, history: list[dict] | None = None) -> dict:
    settings = get_settings()
    history = history or []
    sources = retrieve(db, _search_query(question, history))
    base = {
        "sources": sources,
        "similarity_threshold": settings.similarity_threshold,
        "embedding_backend": settings.embedding_backend,
    }
    if not sources:
        return {
            **base,
            "answer": INSUFFICIENT,
            "answer_mode": "insufficient_context",
        }
    mode = settings.resolved_llm_mode()
    if mode == "gemini":
        prompt = build_prompt(question, sources, history)
        try:
            answer = generate_with_gemini(prompt)
        except Exception as exc:
            # Gemini outages must not turn a usable retrieval result into a
            # failed chat. Show clearly labelled source excerpts instead.
            return {
                **base,
                "answer": quote_retrieved_passages(
                    sources,
                    "Gemini is temporarily unavailable, so CampusCopilot could not generate a summary. "
                    "Here are the retrieved source passages. Please verify the cited document and page; "
                    "these excerpts are not a generated answer.",
                ),
                "answer_mode": "gemini_fallback",
                "llm_error": str(exc),
            }
        return {**base, "answer": answer, "answer_mode": "gemini"}
    if mode == "gemini_missing":
        return {
            **base,
            "answer": (
                "LLM_PROVIDER is set to gemini, but GEMINI_API_KEY is empty. "
                "No generated answer was produced. The retrieved passages are shown below."
            ),
            "answer_mode": "llm_unavailable",
        }
    return {
        **base,
        "answer": quote_retrieved_passages(
            sources,
            "Retrieval-only mode: a language model is not configured, so this reply quotes "
            "the uploaded documents instead of writing a new answer.",
        ),
        "answer_mode": "retrieval_only",
    }
