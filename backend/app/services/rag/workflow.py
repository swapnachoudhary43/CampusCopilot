"""Distinct steps that run before an answer is shown.

These are not separate language-model calls. Each step reads the question,
the site registry, or the retrieved pages and returns its own result.
"""

from difflib import SequenceMatcher

from app.services.rag.lexical import tokens

DEPARTMENTS = (
    ("school of data science", "School of Data Science and Forecasting", ("dsf.dauniv.ac.in",)),
    ("sdsf", "School of Data Science and Forecasting", ("dsf.dauniv.ac.in",)),
    ("data science and forecasting", "School of Data Science and Forecasting", ("dsf.dauniv.ac.in",)),
    ("iips", "International Institute of Professional Studies", ("iips.edu.in",)),
    ("professional studies", "International Institute of Professional Studies", ("iips.edu.in",)),
    ("distance and online", "Centre for Distance and Online Education", ("cdoedavv.ac.in",)),
    ("cdoe", "Centre for Distance and Online Education", ("cdoedavv.ac.in",)),
    ("engineering and technology", "Institute of Engineering and Technology", ("ietdavv.edu.in",)),
    (" iet", "Institute of Engineering and Technology", ("ietdavv.edu.in",)),
    ("school of education", "School of Education", ("edu.dauniv.ac.in",)),
    ("central library", "Central Library", ("lib.dauniv.ac.in",)),
    (" library", "Central Library", ("lib.dauniv.ac.in",)),
    ("student welfare", "Dean of Student Welfare", ("dsw.dauniv.ac.in",)),
    ("placement", "Centralised Placement Cell", ("cpc.dauniv.ac.in",)),
)


def is_latest_request(question: str) -> bool:
    words = tokens(question)
    if any(word in {"latest", "newest", "recent", "lastest"} for word in words):
        return True
    return any(SequenceMatcher(None, word, "latest").ratio() >= 0.78 for word in words)


def is_notice_question(question: str) -> bool:
    words = tokens(question)
    if any(word in {"notice", "notices", "announcement", "announcements", "circular", "circulars", "news"} for word in words):
        return True
    if not is_latest_request(question):
        return False
    return any(
        SequenceMatcher(None, word, candidate).ratio() >= 0.65
        for word in words
        for candidate in ("notice", "notices")
    )


def understand_question(question: str) -> dict:
    lowered = f" {(question or '').lower()} "
    found: list[tuple[str, tuple[str, ...]]] = []
    for needle, name, hosts in DEPARTMENTS:
        if needle in lowered and all(name != existing[0] for existing in found):
            found.append((name, hosts))
    intent = "general"
    asks_exam = any(word in lowered for word in (" exam", "examination", " final "))
    asks_schedule = any(word in lowered for word in ("timetable", "time table", "schedule", "dates"))
    if asks_exam and asks_schedule:
        intent = "exam_schedule"
    elif "attendance" in lowered or "attend" in lowered:
        intent = "attendance_policy"
    elif is_notice_question(question):
        intent = "notices"
    elif any(word in lowered for word in (" where ", " located", " address")):
        intent = "location"
    elif any(word in lowered for word in ("course", "programme", "program", "syllabus", "offered")):
        intent = "courses"
    elif any(word in lowered for word in ("faculty", "professor", "head of")):
        intent = "faculty"
    elif "placement" in lowered or "fee" in lowered:
        intent = "services"
    names = [name for name, _hosts in found]
    hosts = tuple(dict.fromkeys(host for _name, site_hosts in found for host in site_hosts))
    if names:
        detail = f"Department: {', '.join(names)}. Intent: {intent}."
    else:
        detail = f"No specific school was named. Intent: {intent}."
    return {"intent": intent, "departments": names, "hosts": hosts, "detail": detail}


def host_location_evidence(db, understood: dict) -> list[dict]:
    """Pull a campus-address sentence from the named school's own indexed pages."""
    if understood["intent"] != "location" or not understood["hosts"]:
        return []
    from app.models.entities import Document, DocumentChunk

    evidence = []
    for host in understood["hosts"]:
        rows = (
            db.query(DocumentChunk, Document)
            .join(Document)
            .filter(Document.status == "processed", Document.source_url.contains(host))
            .all()
        )
        for chunk, document in rows:
            lowered = chunk.text.lower()
            if "takshila campus" not in lowered and "khandwa road" not in lowered:
                continue
            if "administrative campus" in lowered and "takshila campus" not in lowered:
                continue
            start = lowered.find("takshila campus")
            if start < 0:
                start = lowered.find("khandwa road")
            excerpt = chunk.text[max(0, start - 120) : start + 420]
            evidence.append({
                "document_id": document.id,
                "document_title": document.title,
                "page_number": chunk.page_number,
                "excerpt": excerpt,
                "score": 1,
                "semantic_score": 0,
                "lexical_score": 0,
                "fusion_score": 1,
                "retrieval_method": "department_site",
                "source_url": document.source_url,
                "publication_date": document.publication_date,
                "provenance": document.provenance,
                "document_type": document.document_type,
                "department": document.department,
                "retrieved_at": document.retrieved_at.isoformat() if document.retrieved_at else None,
            })
            break
    return evidence


def focus_department_sources(question: str, sources: list[dict], understood: dict) -> tuple[list[dict], str]:
    hosts = understood["hosts"]
    if not hosts:
        return sources, "University-wide indexed pages were kept."
    names = [name.lower() for name in understood["departments"]]
    matched = []
    for source in sources:
        url = (source.get("source_url") or "").lower()
        label = f"{source.get('department') or ''} {source.get('document_title') or ''}".lower()
        if any(host in url for host in hosts) or any(name in label for name in names):
            matched.append(source)
    if understood["intent"] == "attendance_policy":
        university_policies = [
            source
            for source in sources
            if "dauniv.ac.in" in (source.get("source_url") or "").lower()
            and any(
                marker in (source.get("document_title") or "").lower()
                for marker in ("ordinance", "regulation", "attendance policy")
            )
            and "attendance" in (source.get("excerpt") or "").lower()
        ]
        matched.extend(source for source in university_policies if source not in matched)
    if not matched:
        note = (
            f"No retrieved passage came from {', '.join(understood['departments'])}. "
            "Other departments' pages were excluded."
        )
        if understood["intent"] == "location":
            return sources, note
        return [], note
    if understood["intent"] == "attendance_policy":
        return matched, f"Included {', '.join(understood['departments'])} context and applicable university attendance rules."
    if understood["intent"] == "location":
        text = " ".join((source.get("excerpt") or "") for source in matched).lower()
        if not any(word in text for word in ("takshila", "nalanda", "khandwa", "indore", "address", "campus")):
            return sources, "The department pages did not state an address, so other official evidence was kept."
    return matched, f"Evidence limited to {', '.join(understood['departments'])}."
