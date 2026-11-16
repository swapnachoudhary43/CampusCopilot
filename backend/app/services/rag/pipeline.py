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
from app.services.rag.workflow import (
    focus_department_sources,
    host_location_evidence,
    is_notice_question,
    understand_question,
)
from app.services.rag.vector_store import search_index

INSUFFICIENT = (
    "I couldn't find enough information in the indexed official sources to answer that."
)
_PRONOUN = re.compile(r"\b(it|its|that|those|there|this)\b", re.IGNORECASE)
_CONTENT_START = ("what ", "when ", "where ", "who ", "why ", "how ", "which ", "is ", "are ", "can ", "does ", "do ")
_FOLLOW_START = ("and ", "what about", "how about", "then ", "also ")
_AT_LEAST = re.compile(
    r"attendance\s+at\s+least\s+((?:seventy|eighty|sixty|ninety)(?:[\s-]five)?|\d{1,3})\s*(?:%|percent)",
    re.IGNORECASE,
)
_AT_LEAST_TRAILING = re.compile(r"at\s+least\s+(\d{1,3})\s*%?\s+attendance", re.IGNORECASE)
_PERCENTAGE_VALUE = re.compile(
    r"\b(\d{1,3}|(?:sixty|seventy|eighty|ninety)(?:[\s-]+five)?)\s*(?:%|percent)\b",
    re.IGNORECASE,
)
_ORDINANCE_NUMBER = re.compile(r"ordinance\s*(?:no\.?\s*)?(\d+)\b", re.IGNORECASE)
_WEAK_TERMS = {
    "anything", "something", "everything", "nothing", "happening", "happen", "happens",
    "tomorrow", "today", "tonight", "campus", "there", "here", "someone", "anyone",
}
_NAMED_QUERY_WORD = re.compile(r"\b[A-Z][a-z]{2,}\b")
_LARGE_NUMBER = re.compile(r"\b\d{3,}\b")
_NINTH_SEMESTER = re.compile(r"\b(?:9th|ninth|ix)\s+semester\b", re.IGNORECASE)
_NINTH_SEMESTER_REVISED = re.compile(
    r"\b(?:9th|ninth|ix)\s+semester\s+revised\b",
    re.IGNORECASE,
)
_EXAM_TIME = re.compile(
    r"exam time:\s*(\d{1,2}:\d{2}\s*(?:am|pm)\s*(?:to|[-–])\s*"
    r"\d{1,2}:\d{2}\s*(?:am|pm))",
    re.IGNORECASE,
)
_SCHEDULE_DATE = re.compile(r"\b\d{2}[-/]\d{2}[-/]\d{4}\b")
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


def _query_anchors(query: str) -> set[str]:
    """Keep proper names and explicit large figures from matching unrelated evidence."""
    words = _NAMED_QUERY_WORD.findall(query or "")
    first_word = next(iter(re.findall(r"[A-Za-z]+", query or "")), "")
    anchors = {word.lower() for word in words if word.lower() != first_word.lower()}
    anchors.update(_LARGE_NUMBER.findall(query or ""))
    department_terms = {
        word
        for department in understand_question(query).get("departments", [])
        for word in tokens(department)
    }
    return anchors - department_terms


def _asks_for_exam_schedule(query: str) -> bool:
    lowered = (query or "").lower()
    asks_exam = any(word in lowered for word in ("exam", "examination", "final"))
    asks_timetable = any(word in lowered for word in ("timetable", "time table", "schedule", "dates"))
    return asks_exam and asks_timetable


def _asks_for_notices(query: str) -> bool:
    return is_notice_question(query)


def _is_notice_source(source: dict) -> bool:
    title_url = f"{source.get('document_title') or ''} {source.get('source_url') or ''}".lower()
    if any(word in title_url for word in ("notice", "announcement", "news", "circular")):
        return True
    excerpt = (source.get("excerpt") or "").lower()
    return any(
        heading in excerpt
        for heading in ("official notices", "news and announcements", "latest news", "recent updates")
    )


def _notice_excerpt(text: str, limit: int = 1800) -> str:
    text = " ".join((text or "").split())
    lowered = text.lower()
    markers = (
        "official notices & circulars",
        "official notices and circulars",
        "news and announcements",
        "latest news",
        "recent updates",
    )
    positions = [lowered.find(marker) for marker in markers if lowered.find(marker) >= 0]
    if positions:
        start = min(positions)
        if lowered.find("recent updates") == start:
            issue_date = re.search(
                r"\bissued on\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
                text[:start],
                re.IGNORECASE,
            )
            if issue_date and start - issue_date.end() <= 250:
                start = issue_date.start()
        text = text[start:]
    iips_end = re.search(r"\badmission\s*[-:]?\s*fees structure\b", text, re.IGNORECASE)
    if iips_end:
        text = text[: iips_end.start()]
    return text[:limit].rstrip()


def _join_overlapping_chunks(chunks: list[DocumentChunk]) -> str:
    text = ""
    for chunk in chunks:
        next_text = chunk.text
        overlap_limit = min(len(text), len(next_text), 300)
        overlap = next(
            (size for size in range(overlap_limit, 0, -1) if text.endswith(next_text[:size])),
            0,
        )
        text += next_text[overlap:] if overlap else f" {next_text}"
    return text.strip()


def _department_notice_sources(db: Session, understood: dict) -> list[dict]:
    hosts = understood["hosts"]
    if not hosts:
        return []

    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.status == "processed")
        .all()
    )
    grouped: dict[int, list[DocumentChunk]] = {}
    documents: dict[int, Document] = {}
    for chunk in chunks:
        document = chunk.document
        if not document or not any(host in (document.source_url or "").lower() for host in hosts):
            continue
        grouped.setdefault(document.id, []).append(chunk)
        documents[document.id] = document

    candidates = []
    seen_pages = set()
    for document_id, page_chunks in grouped.items():
        document = documents[document_id]
        page_chunks.sort(key=lambda chunk: chunk.chunk_index)
        full_text = _join_overlapping_chunks(page_chunks)
        candidate = {
            "document_title": document.title,
            "source_url": document.source_url,
            "excerpt": full_text,
        }
        if not _is_notice_source(candidate):
            continue
        excerpt = _notice_excerpt(full_text)
        if not excerpt:
            continue
        url = document.source_url or ""
        page_key = (url.split("?", 1)[0].rstrip("/").lower(), document.title)
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        path = url.split("?", 1)[0].lower()
        priority = int(any(word in path for word in ("notice", "news", "announcement", "circular")))
        lowered_text = full_text.lower()
        priority += int("official notices" in lowered_text or "news and announcements" in lowered_text)
        priority += min(3, len(re.findall(r"\b(?:notices?|circulars?)\b", lowered_text)))
        candidates.append(
            {
                "document_id": document.id,
                "document_title": document.title or url,
                "page_number": 1,
                "excerpt": excerpt,
                "score": 1,
                "semantic_score": 0,
                "lexical_score": 0,
                "fusion_score": 1,
                "retrieval_method": "official_notice_page",
                "source_url": url,
                "publication_date": document.publication_date,
                "provenance": document.provenance,
                "document_type": document.document_type,
                "department": document.department,
                "retrieved_at": document.retrieved_at.isoformat() if document.retrieved_at else None,
                "_priority": priority,
            }
        )

    candidates_by_host: dict[str, list[dict]] = {host: [] for host in hosts}
    for source in candidates:
        host = next(
            (item for item in hosts if item in (source.get("source_url") or "").lower()),
            "",
        )
        if host:
            candidates_by_host[host].append(source)
    for host_candidates in candidates_by_host.values():
        host_candidates.sort(
            key=lambda source: (source["_priority"], source.get("retrieved_at") or ""),
            reverse=True,
        )

    selected = []
    for index in range(2):
        for host in hosts:
            if len(candidates_by_host[host]) <= index:
                continue
            source = candidates_by_host[host][index]
            source.pop("_priority", None)
            selected.append(source)
    return selected


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
    if _asks_for_exam_schedule(lowered):
        if _NINTH_SEMESTER.search(lowered):
            extra.append("IX semester revised end semester examination schedule dates subjects")
        else:
            extra.append("end semester final examination timetable dates subjects")
    elif any(word in lowered for word in ("exam", "examination", "final")):
        extra.append("examination ordinance guideline")
    if _asks_for_notices(lowered):
        extra.append(f"{question} latest news notices announcements circulars")
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


def _merge_sources(groups: list[list[dict]], limit: int, query: str | None = None) -> list[dict]:
    best: dict[tuple, dict] = {}
    for group in groups:
        for source in group:
            key = (source.get("document_id"), source.get("page_number"), source.get("source_url"))
            current = best.get(key)
            if query and _asks_for_exam_schedule(query):
                source_rank = (int(_is_exam_schedule_source(query, source)), source.get("fusion_score") or 0)
                current_rank = (
                    int(_is_exam_schedule_source(query, current)) if current else 0,
                    current.get("fusion_score") or 0 if current else 0,
                )
            elif query and _asks_for_notices(query):
                source_rank = (int(_is_notice_source(source)), source.get("fusion_score") or 0)
                current_rank = (
                    int(_is_notice_source(current)) if current else 0,
                    current.get("fusion_score") or 0 if current else 0,
                )
            else:
                source_rank = (0, source.get("fusion_score") or 0)
                current_rank = (0, current.get("fusion_score") or 0 if current else 0)
            if current is None or source_rank > current_rank:
                best[key] = source
    if query and _asks_for_exam_schedule(query):
        rows = sorted(
            best.values(),
            key=lambda source: (_is_exam_schedule_source(query, source), source.get("fusion_score") or 0),
            reverse=True,
        )
    elif query and _asks_for_notices(query):
        rows = sorted(
            best.values(),
            key=lambda source: (_is_notice_source(source), source.get("fusion_score") or 0),
            reverse=True,
        )
    else:
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


def _filter_named_ordinance_sources(query: str, sources: list[dict]) -> list[dict]:
    if not _asks_for_attendance_figure(query):
        return sources
    numbers = {match.group(1) for match in _ORDINANCE_NUMBER.finditer(query or "")}
    if not numbers:
        return sources
    return [
        source
        for source in sources
        if any(title_has_ordinance(source.get("document_title") or "", number) for number in numbers)
    ]


def _asks_for_attendance_requirement(query: str) -> bool:
    lowered = (query or "").lower()
    asks_attendance = "attendance" in lowered or "attend" in lowered
    asks_requirement = any(
        phrase in lowered
        for phrase in (
            "minimum",
            "percent",
            "percentage",
            "criteria",
            "requirement",
            "required",
            "eligibility",
            "eligible",
            "sit for",
            "appear for",
            "appear at",
            "examination",
            "exam",
        )
    )
    return asks_attendance and asks_requirement


def _asks_about_uploaded_document(query: str) -> bool:
    lowered = (query or "").lower()
    return any(
        phrase in lowered
        for phrase in ("uploaded", "this document", "the document", "according to this policy")
    )


def _official_attendance_sources(db: Session) -> list[dict]:
    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.status == "processed", Document.title.ilike("%ordinance%"))
        .all()
    )
    pages: dict[tuple[int, int], list[DocumentChunk]] = {}
    documents: dict[int, Document] = {}
    for chunk in chunks:
        document = chunk.document
        if (
            not document
            or not document.provenance.startswith("official")
            or not title_has_ordinance(document.title, "6")
        ):
            continue
        documents[document.id] = document
        pages.setdefault((document.id, chunk.page_number), []).append(chunk)

    sources = []
    for (document_id, page_number), page_chunks in sorted(pages.items(), key=lambda item: item[0][1]):
        document = documents[document_id]
        page_chunks.sort(key=lambda chunk: chunk.chunk_index)
        text = _join_overlapping_chunks(page_chunks)
        if (
            "attendance" not in text.lower()
            or not re.search(r"\b(?:at least|minimum)\b", text, re.IGNORECASE)
            or not _PERCENTAGE_VALUE.search(text)
            or not re.search(r"\b(?:lectures?|practicals?|sessional|clinical)\b", text, re.IGNORECASE)
        ):
            continue
        source = _source_from_chunk(page_chunks[0], 0, 0, 1)
        source["page_number"] = page_number
        source["excerpt"] = _window_around_requirement(text, limit=1400)
        source["retrieval_method"] = "official_policy"
        source.pop("_chunk", None)
        sources.append(source)
    return sources[:3]


def _attendance_percentages(clause: str) -> list[str]:
    values = []
    for match in _PERCENTAGE_VALUE.finditer(clause or ""):
        raw = match.group(1).lower().replace("-", " ")
        values.append(_WORD_PERCENT.get(raw, raw))
    return values


def _attendance_policy_answer(question: str, sources: list[dict], understood: dict) -> str | None:
    text = " ".join(source.get("excerpt") or "" for source in sources)
    if not text:
        return None

    study_match = re.search(r"regular\s+course\s+of\s+study", text, re.IGNORECASE)
    if study_match:
        text = text[study_match.start() :]
    general_match = re.search(r"\(a\)\s*(.*?)(?=\(b\)|$)", text, re.IGNORECASE)
    medicine_match = re.search(r"\(b\)\s*(.*?)(?=\(c\)|$)", text, re.IGNORECASE)
    engineering_match = re.search(r"\(c\)\s*(.*?)(?=\bNOTE:|\(v\)|$)", text, re.IGNORECASE)
    general_clause = general_match.group(1) if general_match else ""
    medicine_clause = medicine_match.group(1) if medicine_match else ""
    engineering_clause = engineering_match.group(1) if engineering_match else ""

    if not general_clause:
        general_match = re.search(
            r"(?:in case of faculties other than|faculties other than).{0,240}",
            text,
            re.IGNORECASE,
        )
        general_clause = general_match.group(0) if general_match else ""
    general_values = _attendance_percentages(general_clause)
    medicine_values = _attendance_percentages(medicine_clause)
    engineering_values = _attendance_percentages(engineering_clause)

    general_line = (
        f"Faculties other than Medicine, Ayurveda, and Engineering: at least "
        f"{general_values[0]}% in lectures and practicals separately."
        if general_values
        else None
    )
    medicine_line = (
        f"Medicine and Ayurveda: at least {medicine_values[0]}% in theory and "
        f"{medicine_values[1]}% in practicals and clinical/ward-clinics separately."
        if len(medicine_values) >= 2
        else None
    )
    engineering_line = (
        f"Engineering: at least {engineering_values[-1]}% in lectures and "
        f"practical/sessional work separately."
        if engineering_values
        else None
    )

    lowered = (question or "").lower()
    departments = understood.get("departments") or []
    if "medicine" in lowered or "ayurveda" in lowered:
        lines = [medicine_line] if medicine_line else []
    elif "engineering" in lowered:
        lines = [engineering_line] if engineering_line else []
    elif departments:
        lines = (
            [
                f"For {departments[0]}, the general-category requirement is at least "
                f"{general_values[0]}% in lectures and practicals separately."
            ]
            if general_values
            else []
        )
    else:
        lines = [line for line in (general_line, medicine_line, engineering_line) if line]
        if len(lines) != 3:
            return None

    if not lines:
        return None
    return "Under DAVV Ordinance No. 6:\n" + "\n".join(f"- {line}" for line in lines) + " [1]"


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
    lowered = (query or "").lower()
    if _asks_for_exam_schedule(lowered):
        if _NINTH_SEMESTER.search(lowered):
            match = _NINTH_SEMESTER_REVISED.search(text) or _NINTH_SEMESTER.search(text)
        else:
            match = re.search(
                r"semester end examination schedule|end semester.{0,30}(?:time\s*table|timetable)|"
                r"final examination.{0,30}(?:time\s*table|timetable|schedule)",
                text,
                re.IGNORECASE,
            )
        if match:
            excerpt = text[match.start() : match.start() + 900]
            next_program = re.search(
                r"\b(?:M\.?\s*Sc\.?|MBA\s*\(|Executive M\.?\s*Tech)",
                excerpt,
                re.IGNORECASE,
            )
            if next_program:
                excerpt = excerpt[: next_program.start()]
            exam_time = _EXAM_TIME.search(text)
            if exam_time:
                return f"Exam time: {exam_time.group(1)}.\n{excerpt}"
            return excerpt
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


def _is_exam_schedule_source(query: str, source: dict) -> bool:
    title = (source.get("document_title") or "").lower()
    excerpt = source.get("excerpt") or ""
    text = f"{title} {excerpt}"
    lowered = text.lower()
    if "class timetable" in title or "class time table" in title:
        return False
    if len(_SCHEDULE_DATE.findall(excerpt)) < 2:
        return False
    if _NINTH_SEMESTER.search(query):
        return bool(_NINTH_SEMESTER_REVISED.search(text))
    return bool(
        re.search(
            r"semester end examination schedule|end semester.{0,30}(?:time\s*table|timetable)|"
            r"final examination.{0,30}(?:time\s*table|timetable|schedule)",
            lowered,
        )
    )


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
        if _asks_for_exam_schedule(query):
            page_number = rows[0]["_chunk"].page_number
            page_chunks = [
                chunk
                for chunk in rows[0]["_chunk"].document.chunks
                if chunk.page_number == page_number
            ]
            page_chunks.sort(key=lambda chunk: chunk.chunk_index)
            if _NINTH_SEMESTER.search(query):
                schedule_chunk = next(
                    (chunk for chunk in page_chunks if _NINTH_SEMESTER_REVISED.search(chunk.text)),
                    None,
                )
                if schedule_chunk:
                    full_page_text = " ".join(chunk.text for chunk in page_chunks)
                    exam_time = _EXAM_TIME.search(full_page_text)
                    prefix = f"Exam time: {exam_time.group(1)} " if exam_time else ""
                    text = f"{prefix}{schedule_chunk.text}"
                else:
                    text = " ".join(chunk.text for chunk in page_chunks)
            else:
                text = " ".join(chunk.text for chunk in page_chunks)
        else:
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
    anchors = _query_anchors(query)
    for chunk_id, fusion in sorted(fused.items(), key=lambda item: item[1], reverse=True):
        chunk = by_id.get(chunk_id)
        if chunk is None or chunk.document is None:
            continue
        available_terms = set(tokens(f"{chunk.text} {chunk.document.title}"))
        if not anchors.issubset(available_terms):
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
            available_terms = set(tokens(f"{chunk.text} {chunk.document.title}"))
            if not anchors.issubset(available_terms):
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
    if understood["departments"] and understood["intent"] == "exam_schedule":
        semester = "IX semester" if _NINTH_SEMESTER.search(question) else "end semester"
        search_text = f"{search_text}\n{understood['departments'][0]} {semester} examination schedule"
    elif understood["departments"] and understood["intent"] == "notices":
        search_text = f"{search_text}\n{understood['departments'][0]} latest notices news announcements"
    elif understood["departments"] and understood["intent"] == "attendance_policy":
        search_text = f"{search_text}\n{understood['departments'][0]} attendance minimum ordinance faculty requirements"
    elif understood["departments"] and understood["intent"] in {"location", "courses", "faculty", "services"}:
        search_text = f"{search_text}\n{understood['departments'][0]} address campus"
    sources = retrieve(db, search_text)
    extras = expanded_queries(question)
    if extras:
        groups = [sources]
        for extra in extras[:4]:
            groups.append(retrieve(db, extra))
        sources = _merge_sources(groups, settings.retrieval_top_k, question)
    direct = host_location_evidence(db, understood)
    if direct:
        seen = {(item.get("source_url"), item.get("page_number")) for item in direct}
        sources = direct + [item for item in sources if (item.get("source_url"), item.get("page_number")) not in seen]
    sources, department_note = focus_department_sources(question, sources, understood)
    sources = _filter_named_ordinance_sources(search_text, sources)
    if (
        understood["intent"] == "attendance_policy"
        and _asks_for_attendance_requirement(question)
        and not _asks_about_uploaded_document(question)
    ):
        official_sources = _official_attendance_sources(db)
        if official_sources:
            sources = official_sources
        else:
            sources = []
            department_note = "No official DAVV Ordinance No. 6 attendance rule is indexed."
    if understood["intent"] == "exam_schedule":
        sources = [source for source in sources if _is_exam_schedule_source(question, source)]
        if not sources:
            department_note = (
                "No readable final-examination schedule rows were found for the named department. "
                "Class timetables were excluded."
            )
    elif understood["intent"] == "notices":
        notice_sources = _department_notice_sources(db, understood)
        sources = notice_sources or [source for source in sources if _is_notice_source(source)]
        if not sources:
            department_note = "No official notice, news, or circular page matched this question."
    sources = prefer_location_sources(question, sources)
    workflow.extend([
        {"name": "Document retrieval", "task": "Hybrid search of indexed official pages", "status": "completed", "detail": f"{len(sources)} passages kept."},
        {"name": "Department research", "task": "Prefer the named school's own site", "status": "completed", "detail": department_note},
        {"name": "Evidence verification", "task": "Reject timings, addresses, and conflicts that the text does not support", "status": "completed", "detail": "Checked retrieved passages before generation."},
    ])
    unread = _unread_exam_files(db, question) if understood["intent"] == "exam_schedule" else []
    base = {
        "sources": sources,
        "similarity_threshold": settings.similarity_threshold,
        "embedding_backend": settings.embedding_backend,
        "workflow": workflow,
    }
    hours_gap = library_hours_gap(question, sources)
    if hours_gap:
        return {**base, "answer": hours_gap, "answer_mode": "insufficient_context"}
    if unread and not any(_is_exam_schedule_source(question, source) for source in sources):
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
                "I found a matching timetable PDF, but it is scanned and cannot be searched. "
                "No readable schedule rows were available."
            ),
            "answer_mode": "needs_ocr",
        }
    if not sources:
        return {**base, "answer": INSUFFICIENT, "answer_mode": "insufficient_context"}
    if understood["intent"] == "attendance_policy":
        answer = _attendance_policy_answer(question, sources, understood)
        if answer:
            return {**base, "answer": answer, "answer_mode": "policy"}
    note = _conflict_note(sources)
    mode = settings.resolved_llm_mode()
    if mode == "gemini":
        prompt = build_prompt(question, sources, history)
        try:
            answer = generate_with_gemini(prompt)
        except GeminiError as exc:
            answer = quote_retrieved_passages(
                sources,
                exc.user_message,
                excerpt_limit=320 if understood["intent"] == "notices" else None,
            )
            if note:
                answer = f"{answer}\n\n{note}"
            return {**base, "answer": answer, "answer_mode": "llm_unavailable"}
        if note:
            answer = f"{answer}\n\n{note}"
        return {**base, "answer": answer, "answer_mode": "gemini"}
    if mode == "gemini_missing":
        answer = quote_retrieved_passages(
            sources,
            "I can't generate an answer right now. Relevant source text:",
            excerpt_limit=320 if understood["intent"] == "notices" else None,
        )
        return {**base, "answer": answer, "answer_mode": "llm_unavailable"}
    answer = quote_retrieved_passages(
        sources,
        "",
        excerpt_limit=320 if understood["intent"] == "notices" else None,
    )
    if note:
        answer = f"{answer}\n\n{note}"
    return {**base, "answer": answer, "answer_mode": "retrieval_only"}
