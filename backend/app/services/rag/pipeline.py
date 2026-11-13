"""Retrieval-augmented answering.

Semantic search and BM25 are fused with reciprocal rank fusion. A single
cosine cutoff is not the only way a passage can be kept, and an RRF value
is never reported as similarity.
"""

import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Document, DocumentChunk, Event
from app.utils.time import ensure_aware, utcnow
from app.services.rag.embeddings import get_embedder
from app.services.rag.generator import GeminiError, build_prompt, generate_with_gemini, quote_retrieved_passages
from app.services.rag.lexical import bm25_ranks, reciprocal_rank_fusion, tokens
from app.services.rag.workflow import focus_department_sources, host_location_evidence, understand_question
from app.services.rag.vector_store import search_index

INSUFFICIENT = (
    "The indexed official sources do not contain enough information to answer this question. "
    "I will not guess a rule, date, fee, timing, or address."
)
_PRONOUN = re.compile(r"\b(it|its|that|those|there|this)\b", re.IGNORECASE)
_CONTENT_START = ("what ", "when ", "where ", "who ", "why ", "how ", "which ", "is ", "are ", "can ", "does ", "do ")
_FOLLOW_START = ("and ", "what about", "how about", "then ", "also ")
_AT_LEAST = re.compile(
    r"attendance\s+at\s+least\s+((?:seventy|eighty|sixty|ninety)(?:[\s-]five)?|\d{1,3})\s*(?:%|percent)",
    re.IGNORECASE,
)
_AT_LEAST_TRAILING = re.compile(r"at\s+least\s+(\d{1,3})\s*%?\s+attendance", re.IGNORECASE)
_ORDINANCE_NUMBER = re.compile(r"ordinance\s*(?:no\.?\s*)?(\d+)\b", re.IGNORECASE)
_WEAK_TERMS = {
    "anything", "something", "everything", "nothing", "happening", "happen", "happens",
    "tomorrow", "today", "tonight", "campus", "there", "here", "someone", "anyone",
}
_LOCAL_ZONE = ZoneInfo("Asia/Kolkata")
_WORD_PERCENT = {
    "sixty": "60",
    "sixty five": "65",
    "seventy": "70",
    "seventy five": "75",
    "eighty": "80",
    "eighty five": "85",
    "ninety": "90",
}


def specific_term_overlap(query: str, text: str) -> bool:
    """A lexical hit must share a real subject word, not only 'anything' or 'campus'."""
    overlap = set(tokens(query)) & set(tokens(text))
    return bool(overlap - _WEAK_TERMS)


def asks_for_schedule(question: str) -> bool:
    lowered = (question or "").lower()
    has_time = any(word in lowered for word in ("tomorrow", "today", "tonight", "this week", "this weekend"))
    has_event = any(word in lowered for word in ("happen", "event", "campus", "schedule", "programme", "program", "going on"))
    return has_time and has_event


def _schedule_dates(question: str, now) -> set:
    local_today = now.astimezone(_LOCAL_ZONE).date()
    lowered = question.lower()
    if "tomorrow" in lowered:
        return {local_today + timedelta(days=1)}
    if "today" in lowered or "tonight" in lowered:
        return {local_today}
    if "this weekend" in lowered:
        saturday = local_today + timedelta(days=(5 - local_today.weekday()) % 7)
        return {saturday, saturday + timedelta(days=1)}
    return {local_today + timedelta(days=offset) for offset in range(7)}


def _event_line(event: Event) -> str:
    start = ensure_aware(event.starts_at).astimezone(_LOCAL_ZONE)
    label = " DEMO DATA, not a DAVV event." if event.is_demo else ""
    return f"- {event.title} at {event.venue} on {start.strftime('%d %b %Y %H:%M')} IST.{label}"


def schedule_answer(db: Session, question: str) -> str | None:
    """Answer a today/tomorrow question from the event rows, not from ordinances."""
    if not asks_for_schedule(question):
        return None
    now = utcnow()
    wanted = _schedule_dates(question, now)
    events = db.query(Event).order_by(Event.starts_at.asc()).all()
    matched = [event for event in events if ensure_aware(event.starts_at).astimezone(_LOCAL_ZONE).date() in wanted]
    upcoming = [event for event in events if ensure_aware(event.starts_at) > now]
    if matched:
        lines = ["These items are on the campus event schedule for that day:"]
        lines.extend(_event_line(event) for event in matched)
        return "\n".join(lines)
    lines = ["Nothing in the campus event schedule falls on that day. I will not invent a programme from policy documents."]
    if upcoming:
        lines.append("The next scheduled items are:")
        lines.extend(_event_line(event) for event in upcoming[:3])
    return "\n".join(lines)


def expanded_queries(question: str) -> list[str]:
    """Extra searches for a broad question. These are retrieval terms, not an answer."""
    lowered = question.lower()
    if "ordinance" in lowered and "attendance" in lowered:
        return []
    extra: list[str] = []
    if "facilit" in lowered:
        extra.extend([
            "library hostel sports laboratory medical transport student facility",
            "central library",
            "hostel facility",
            "sports facility ground",
        ])
    if "library" in lowered and any(word in lowered for word in ("time", "timing", "hour", "open", "close", "its")):
        extra.append("library working hours opening hours schedule central library")
    if any(word in lowered for word in ("where", "located", "location", "address")):
        extra.append(f"{question} address campus contact")
    if "hostel" in lowered:
        extra.append("hostel accommodation facility")
    if "admission" in lowered:
        extra.append("admission procedure guideline")
    if "exam" in lowered:
        extra.append("examination ordinance guideline")
    if "notice" in lowered:
        extra.append("official notice circular announcement")
    if "contact" in lowered or "administration" in lowered:
        extra.append("contact registrar office telephone email administration")
    if "sport" in lowered:
        extra.append("sports facilities ground gymnasium")
    if "laborator" in lowered:
        extra.append("laboratory facilities department")
    if "migration" in lowered:
        extra.append("migration certificate procedure")
    if "calendar" in lowered:
        extra.append("academic calendar")
    if "attendance" in lowered and any(word in lowered for word in ("below", "short", "less", "shortage")):
        extra.append("shortage of attendance condonation debarred")
    return extra


def prefer_location_sources(query: str, sources: list[dict]) -> list[dict]:
    lowered = query.lower()
    if not any(word in lowered for word in ("where", "located", "location", "address")):
        return sources

    def address_like(source: dict) -> bool:
        text = (source.get("excerpt") or "").lower()
        return any(word in text for word in ("takshila", "nalanda", "khandwa", "pin", "452001", "address"))

    def timetable(source: dict) -> bool:
        text = f"{source.get('excerpt') or ''} {source.get('document_title') or ''}".lower()
        return "timetable" in text or "time table" in text

    addresses = [source for source in sources if address_like(source) and not timetable(source)]
    if addresses:
        return addresses
    remaining = [source for source in sources if not timetable(source)]
    return remaining or sources


def _merge_sources(groups: list[list[dict]], limit: int) -> list[dict]:
    best: dict[tuple, dict] = {}
    for group in groups:
        for source in group:
            key = (source.get("document_id"), source.get("page_number"), source.get("source_url"))
            current = best.get(key)
            if current is None or (source.get("fusion_score") or 0) > (current.get("fusion_score") or 0):
                best[key] = source
    rows = sorted(best.values(), key=lambda source: source.get("fusion_score") or 0, reverse=True)
    return rows[:limit]


def _search_query(question: str, history: list[dict]) -> str:
    text = question.strip()
    lowered = text.lower()
    previous = [item["content"] for item in history if item["role"] == "user"]
    if previous and _PRONOUN.search(lowered):
        return f"{previous[-1]}\n{text}"
    starts_follow = lowered.startswith(_FOLLOW_START)
    looks_complete = lowered.startswith(_CONTENT_START)
    short = len(text) < 24 and not looks_complete
    if not starts_follow and not short:
        return text
    previous = [item["content"] for item in history if item["role"] == "user"]
    if not previous:
        return text
    current = set(tokens(text))
    earlier = set(tokens(previous[-1]))
    # "Fee?" after an attendance question is a new subject. Glue only when the
    # fragment has no new content word, or the user explicitly continued.
    if current and current.isdisjoint(earlier) and not starts_follow:
        return text
    return f"{previous[-1]}\n{text}"


def requirement_numbers(text: str) -> set[str]:
    """Percentages written as an attendance minimum, in digits or words."""
    found: set[str] = set()
    for match in _AT_LEAST.finditer(text or ""):
        raw = match.group(1).lower().replace("-", " ")
        found.add(_WORD_PERCENT.get(raw, raw))
    for match in _AT_LEAST_TRAILING.finditer(text or ""):
        found.add(match.group(1))
    return {item for item in found if item.isdigit()}


def named_ordinance(query: str) -> str | None:
    match = _ORDINANCE_NUMBER.search(query or "")
    return match.group(1) if match else None


def title_has_ordinance(title: str, number: str) -> bool:
    return re.search(rf"\bordinance\b(?:\s+no\.?)?\s+{re.escape(number)}\b", title or "", re.IGNORECASE) is not None


def _states_address(query: str, text: str) -> bool:
    lowered = (query or "").lower()
    if not any(word in lowered for word in ("where", "located", "location", "address")):
        return False
    return bool(re.search(r"takshila campus|nalanda campus|khandwa road", text or "", re.IGNORECASE))


def _asks_for_attendance_figure(query: str) -> bool:
    lowered = (query or "").lower()
    return "attendance" in lowered or "percent" in lowered


def _window_around_requirement(text: str, limit: int = 900) -> str:
    match = _AT_LEAST.search(text) or _AT_LEAST_TRAILING.search(text)
    if match is None:
        return text[:limit]
    start = max(0, match.start() - 220)
    return text[start : start + limit]


def _excerpt_for(text: str, query: str) -> str:
    if _asks_for_attendance_figure(query):
        window = _window_around_requirement(text)
        if window != text[:900]:
            return window
    lowered = (query or "").lower()
    if any(word in lowered for word in ("where", "located", "location", "address", "contact")):
        haystack = text.lower()
        for needle in ("takshila campus", "address", "khandwa", "nalanda campus", "pin"):
            index = haystack.find(needle)
            if index >= 0:
                return text[max(0, index - 160) : index + 740]
    return text[:900]


def library_hours_gap(query: str, sources: list[dict]) -> str | None:
    """A library mention is not an opening time."""
    lowered = (query or "").lower()
    asks_hours = "library" in lowered and any(word in lowered for word in ("time", "timing", "hour", "open", "close"))
    if not asks_hours:
        return None
    for source in sources:
        text = f"{source.get('excerpt') or ''} {source.get('document_title') or ''}".lower()
        if "library" not in text:
            continue
        if re.search(r"\b(\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|working hours|opening hours|closing time)\b", text):
            return None
    return (
        "The indexed official pages mention a library, but none of the retrieved text states "
        "opening or closing times. I will not guess a library timing."
    )


def _source_from_chunk(chunk: DocumentChunk, semantic: float, lexical: float, fusion: float) -> dict:
    document = chunk.document
    return {
        "document_id": document.id,
        "document_title": document.title,
        "page_number": chunk.page_number,
        "excerpt": "",
        "score": round(semantic, 4),
        "semantic_score": round(semantic, 4),
        "lexical_score": round(lexical, 4),
        "fusion_score": round(fusion, 6),
        "retrieval_method": "hybrid",
        "source_url": document.source_url,
        "publication_date": document.publication_date,
        "provenance": document.provenance,
        "document_type": document.document_type,
        "department": document.department,
        "retrieved_at": document.retrieved_at.isoformat() if document.retrieved_at else None,
        "_chunk": chunk,
    }


def _page_tier(text: str, title: str, query: str) -> int:
    """Prefer the page that states the figure in the ordinance the user named."""
    if not _asks_for_attendance_figure(query):
        return 0
    has_figure = bool(requirement_numbers(text))
    number = named_ordinance(query)
    named = bool(number and title_has_ordinance(title, number))
    if has_figure and named:
        return 3
    if has_figure:
        return 2
    if named:
        return 1
    return 0


def _group_pages(parts: list[dict], query: str) -> list[dict]:
    grouped: dict[tuple[int, int], list[dict]] = {}
    for item in parts:
        chunk = item["_chunk"]
        grouped.setdefault((chunk.document_id, chunk.page_number), []).append(item)
    pages = []
    for rows in grouped.values():
        rows.sort(key=lambda item: item["_chunk"].chunk_index)
        best = max(rows, key=lambda item: ( _page_tier(item["_chunk"].text, item["document_title"], query), item["fusion_score"]))
        text = " ".join(item["_chunk"].text for item in rows)
        page = dict(best)
        page["excerpt"] = _excerpt_for(text, query)
        page["semantic_score"] = round(max(item["semantic_score"] for item in rows), 4)
        page["lexical_score"] = round(max(item["lexical_score"] for item in rows), 4)
        page["score"] = page["semantic_score"]
        page["_tier"] = _page_tier(text, page["document_title"], query)
        page.pop("_chunk", None)
        pages.append(page)
    pages.sort(key=lambda item: (item["_tier"], item["fusion_score"]), reverse=True)
    has_figure = any(page["_tier"] >= 2 for page in pages)
    chosen = []
    per_document: dict[int, int] = {}
    for page in pages:
        if has_figure and page["_tier"] == 0:
            continue
        count = per_document.get(page["document_id"], 0)
        if count >= 2 and len({item["document_id"] for item in pages}) > 1:
            continue
        per_document[page["document_id"]] = count + 1
        page.pop("_tier", None)
        chosen.append(page)
        if len(chosen) >= get_settings().retrieval_top_k:
            break
    return chosen


def _unread_exam_files(db: Session, query: str) -> list[Document]:
    wanted = set(tokens(query))
    lowered = query.lower()
    asks_exam = any(word in lowered for word in ("exam", "examination", "final"))
    if not asks_exam:
        return []
    if any(word in lowered for word in ("9th", "ninth", " ix ", "semester ix", "ix semester")) or "ix" in wanted:
        wanted.update({"ix", "ninth"})
    matches = []
    rows = db.query(Document).filter(Document.status == "needs_ocr").all()
    for document in rows:
        title = document.title.lower()
        title_tokens = set(tokens(document.title))
        asks_ninth = "9th" in lowered or "ninth" in lowered or " ix " in f" {lowered} "
        if asks_ninth and ("ix" in title_tokens or "ninth" in title):
            matches.append(document)
            continue
        overlap = wanted & title_tokens
        if overlap and any(word in title for word in ("exam", "time table", "timetable")):
            matches.append(document)
    return matches


def retrieve(db: Session, query: str) -> list[dict]:
    settings = get_settings()
    embedder = get_embedder()
    vector = embedder.embed([query])[0]
    try:
        semantic_hits = search_index(vector, max(settings.retrieval_top_k * 8, 24))
    except RuntimeError:
        semantic_hits = []
    semantic = {chunk_id: score for chunk_id, score in semantic_hits}
    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.status == "processed")
        .all()
    )
    lexical_hits = bm25_ranks([(chunk.id, chunk.text) for chunk in chunks], query, top_k=24)
    lexical = {chunk_id: score for chunk_id, score in lexical_hits}
    fused = reciprocal_rank_fusion([
        [chunk_id for chunk_id, _score in semantic_hits],
        [chunk_id for chunk_id, _score in lexical_hits],
    ])
    by_id = {chunk.id: chunk for chunk in chunks}
    accepted = []
    for chunk_id, fusion in sorted(fused.items(), key=lambda item: item[1], reverse=True):
        chunk = by_id.get(chunk_id)
        if chunk is None or chunk.document is None:
            continue
        semantic_score = float(semantic.get(chunk_id, 0.0))
        lexical_score = float(lexical.get(chunk_id, 0.0))
        query_terms = set(tokens(query))
        overlap = len(query_terms & set(tokens(chunk.text)))
        semantic_ok = semantic_score >= settings.similarity_threshold
        lexical_ok = lexical_score >= 1.2 and overlap >= 2 and specific_term_overlap(query, chunk.text)
        states_requirement = _asks_for_attendance_figure(query) and bool(requirement_numbers(chunk.text))
        states_address = _states_address(query, chunk.text)
        if not semantic_ok and not lexical_ok and not states_requirement and not states_address:
            continue
        accepted.append(_source_from_chunk(chunk, semantic_score, lexical_score, fusion))
        if len(accepted) >= 30:
            break
    if _asks_for_attendance_figure(query) or any(word in query.lower() for word in ("where", "located", "location", "address")):
        seen = {item["_chunk"].id for item in accepted}
        for chunk in chunks:
            if chunk.id in seen:
                continue
            if not requirement_numbers(chunk.text) and not _states_address(query, chunk.text):
                continue
            accepted.append(
                _source_from_chunk(
                    chunk,
                    float(semantic.get(chunk.id, 0.0)),
                    float(lexical.get(chunk.id, 0.0)),
                    float(fused.get(chunk.id, 0.0)),
                )
            )
    return _group_pages(accepted, query)


def _conflict_note(sources: list[dict]) -> str:
    by_document: dict[str, set[str]] = {}
    for source in sources:
        numbers = requirement_numbers(source.get("excerpt") or "")
        if numbers:
            by_document.setdefault(source["document_title"], set()).update(numbers)
    notes = []
    if any(len(numbers) > 1 for numbers in by_document.values()):
        notes.append(
            "The retrieved ordinance gives more than one attendance minimum for different faculties. "
            "Those figures were not collapsed into a single percentage."
        )
    titles = list(by_document)
    for left in range(len(titles)):
        for right in range(left + 1, len(titles)):
            if by_document[titles[left]].isdisjoint(by_document[titles[right]]):
                notes.append(
                    "Different documents state different attendance minimums. "
                    "They were not merged. Compare the document titles and publication dates."
                )
                return " ".join(notes)
    return " ".join(notes)


def answer_question(db: Session, question: str, history: list[dict] | None = None) -> dict:
    settings = get_settings()
    history = history or []
    understood = understand_question(question)
    workflow = [
        {"name": "Query understanding", "task": "Identify the school and the kind of question", "status": "completed", "detail": understood["detail"]},
    ]
    scheduled = schedule_answer(db, question)
    if scheduled is not None:
        workflow.append({"name": "University services", "task": "Read the event schedule", "status": "completed", "detail": "Answered from event rows. Policy PDFs were not used."})
        workflow.append({"name": "Document retrieval", "task": "Search indexed pages", "status": "skipped", "detail": "A today or tomorrow question is not answered from ordinances."})
        return {
            "sources": [],
            "similarity_threshold": settings.similarity_threshold,
            "embedding_backend": settings.embedding_backend,
            "answer": scheduled,
            "answer_mode": "schedule",
            "workflow": workflow,
        }
    search_text = _search_query(question, history)
    if understood["departments"] and understood["intent"] in {"location", "courses", "faculty", "services"}:
        search_text = f"{search_text}\n{understood['departments'][0]} address campus"
    sources = retrieve(db, search_text)
    extras = expanded_queries(question)
    if extras:
        groups = [sources]
        for extra in extras[:4]:
            groups.append(retrieve(db, extra))
        sources = _merge_sources(groups, max(settings.retrieval_top_k, 8))
    sources = prefer_location_sources(question, sources)
    direct = host_location_evidence(db, understood)
    if direct:
        seen = {(item.get("source_url"), item.get("page_number")) for item in direct}
        sources = direct + [item for item in sources if (item.get("source_url"), item.get("page_number")) not in seen]
    sources, department_note = focus_department_sources(question, sources, understood)
    workflow.extend([
        {"name": "Document retrieval", "task": "Hybrid search of indexed official pages", "status": "completed", "detail": f"{len(sources)} passages kept."},
        {"name": "Department research", "task": "Prefer the named school's own site", "status": "completed", "detail": department_note},
        {"name": "Evidence verification", "task": "Reject timings, addresses, and conflicts that the text does not support", "status": "completed", "detail": "Checked retrieved passages before generation."},
    ])
    unread = _unread_exam_files(db, question)
    base = {
        "sources": sources,
        "similarity_threshold": settings.similarity_threshold,
        "embedding_backend": settings.embedding_backend,
        "workflow": workflow,
    }
    hours_gap = library_hours_gap(question, sources)
    if hours_gap:
        return {**base, "answer": hours_gap, "answer_mode": "insufficient_context"}
    if unread and not any("end semester" in source["document_title"].lower() or "examination" in source["document_title"].lower() for source in sources):
        names = "; ".join(document.title for document in unread)
        return {
            **base,
            "sources": [
                {
                    "document_id": document.id,
                    "document_title": document.title,
                    "page_number": None,
                    "excerpt": document.status_message or "This PDF has no text layer.",
                    "score": 0,
                    "semantic_score": 0,
                    "lexical_score": 0,
                    "fusion_score": 0,
                    "retrieval_method": "title_only",
                    "source_url": document.source_url,
                    "publication_date": document.publication_date,
                    "provenance": document.provenance,
                }
                for document in unread
            ],
            "answer": (
                "A matching file is stored, but it appears to be a scanned PDF and cannot be searched "
                f"because OCR is unavailable: {names}. Class timetables were not substituted for it."
            ),
            "answer_mode": "needs_ocr",
        }
    if not sources:
        return {**base, "answer": INSUFFICIENT, "answer_mode": "insufficient_context"}
    note = _conflict_note(sources)
    mode = settings.resolved_llm_mode()
    if mode == "gemini":
        prompt = build_prompt(question, sources, history)
        try:
            answer = generate_with_gemini(prompt)
        except GeminiError as exc:
            answer = quote_retrieved_passages(sources, exc.user_message)
            if note:
                answer = f"{answer}\n\n{note}"
            return {**base, "answer": answer, "answer_mode": "llm_unavailable"}
        if note:
            answer = f"{answer}\n\n{note}"
        return {**base, "answer": answer, "answer_mode": "gemini"}
    if mode == "gemini_missing":
        answer = quote_retrieved_passages(
            sources,
            "LLM_PROVIDER is set to gemini, but GEMINI_API_KEY is empty. No generated answer was produced.",
        )
        return {**base, "answer": answer, "answer_mode": "llm_unavailable"}
    answer = quote_retrieved_passages(
        sources,
        "Retrieval-only mode: a language model is not configured, so this reply quotes "
        "the uploaded documents instead of writing a new answer.",
    )
    if note:
        answer = f"{answer}\n\n{note}"
    return {**base, "answer": answer, "answer_mode": "retrieval_only"}
