"""Hybrid retrieval-augmented answering.

Semantic FAISS search handles paraphrases; BM25 keyword retrieval catches
exact policy terms and numbers that embedding similarity can rank too low.
Reciprocal-rank fusion combines both without treating raw scores as equivalent.
"""

import math
import re
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Document, DocumentChunk
from app.services.rag.embeddings import get_embedder
from app.services.rag.generator import build_prompt, generate_with_gemini, quote_retrieved_passages
from app.services.rag.vector_store import search_index

INSUFFICIENT = (
    "The uploaded institutional documents do not contain enough information to answer this question. "
    "I will not guess a rule, date, or fee."
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "at", "is", "are",
    "was", "be", "this", "that", "it", "my", "me", "what", "how", "when", "where",
    "who", "why", "do", "does", "did", "with", "from", "by", "about", "under",
    "required", "require", "need", "needs", "please", "tell", "give", "state",
}
_SYNONYMS = {
    "percentage": {"percent"},
    "percent": {"percentage"},
    "attendance": {"attend"},
    "attend": {"attendance"},
    "requirement": {"required"},
    "requirements": {"required"},
    "minimum": {"min"},
}


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall((text or "").lower()) if token not in _STOPWORDS]


def _expanded_query_tokens(query: str) -> list[str]:
    terms = set(_tokens(query))
    for term in list(terms):
        terms.update(_SYNONYMS.get(term, set()))
    return sorted(terms)


def _lexical_rank(chunks: list[DocumentChunk], query: str) -> list[tuple[int, float]]:
    """Rank indexed chunks using BM25; campus corpora are small enough in-process."""
    if not chunks:
        return []
    terms = _expanded_query_tokens(query)
    if not terms:
        return []

    tokenized = [_tokens(chunk.text) for chunk in chunks]
    lengths = [len(tokens) for tokens in tokenized]
    average_length = sum(lengths) / max(len(lengths), 1)
    document_frequency = Counter()
    counters = []
    for tokens in tokenized:
        counts = Counter(tokens)
        counters.append(counts)
        document_frequency.update(set(counts))

    total = len(chunks)
    scored = []
    for chunk, counts, length in zip(chunks, counters, lengths):
        score = 0.0
        for term in terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * length / max(average_length, 1))
            score += idf * (frequency * 2.5) / denominator

        title_terms = set(_tokens(chunk.document.title if chunk.document else ""))
        score += 0.35 * len(title_terms.intersection(terms))
        if score > 0:
            scored.append((chunk.id, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _search_query(question: str, history: list[dict]) -> str:
    text = question.strip()
    lowered = text.lower()
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
    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.status == "processed")
        .all()
    )
    if not chunks:
        return []

    embedder = get_embedder()
    vector = embedder.embed([query])[0]
    candidate_k = max(32, settings.retrieval_top_k * 8)
    semantic_hits = search_index(vector, candidate_k)
    lexical_hits = _lexical_rank(chunks, query)

    # Reciprocal-rank fusion combines rankings without comparing raw score scales.
    fusion_constant = 60
    fused = defaultdict(float)
    semantic_scores = {}
    lexical_scores = {}
    chunk_by_id = {chunk.id: chunk for chunk in chunks}

    for rank, (chunk_id, score) in enumerate(semantic_hits, start=1):
        if chunk_id in chunk_by_id:
            fused[chunk_id] += 1.0 / (fusion_constant + rank)
            semantic_scores[chunk_id] = float(score)

    for rank, (chunk_id, score) in enumerate(lexical_hits[:candidate_k], start=1):
        fused[chunk_id] += 1.0 / (fusion_constant + rank)
        lexical_scores[chunk_id] = float(score)

    ranked_ids = sorted(fused, key=fused.get, reverse=True)
    grouped = defaultdict(list)
    for chunk_id in ranked_ids:
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None or chunk.document is None or chunk.document.status != "processed":
            continue
        semantic_score = semantic_scores.get(chunk_id, 0.0)
        lexical_score = lexical_scores.get(chunk_id, 0.0)
        # A below-threshold semantic hit survives only if keyword retrieval
        # independently found matching terms in that passage.
        if semantic_score < settings.similarity_threshold and lexical_score <= 0:
            continue
        grouped[(chunk.document_id, chunk.page_number)].append(
            (fused[chunk_id], semantic_score, chunk)
        )

    sources = []
    for parts in grouped.values():
        parts.sort(key=lambda item: item[0], reverse=True)
        selected = parts[:3]
        selected.sort(key=lambda item: item[2].chunk_index)
        first = selected[0][2]
        excerpt = " ".join(item[2].text for item in selected)[:1400]
        sources.append(
            {
                "document_id": first.document_id,
                "document_title": first.document.title,
                "page_number": first.page_number,
                "excerpt": excerpt,
                "score": round(max(item[1] for item in parts), 4),
                "retrieval_score": round(max(item[0] for item in parts), 6),
                "retrieval_method": "hybrid",
            }
        )

    sources.sort(key=lambda item: item["retrieval_score"], reverse=True)
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
        return {**base, "answer": INSUFFICIENT, "answer_mode": "insufficient_context"}
    mode = settings.resolved_llm_mode()
    if mode == "gemini":
        prompt = build_prompt(question, sources, history)
        try:
            answer = generate_with_gemini(prompt)
        except Exception as exc:
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
