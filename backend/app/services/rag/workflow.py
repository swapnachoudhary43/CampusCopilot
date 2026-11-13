"""Distinct steps that run before an answer is shown.

These are not separate language-model calls. Each step reads the question,
the site registry, or the retrieved pages and returns its own result.
"""

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
    ("central library", "Central Library", ("lib.dauniv.ac.in", "edu.dauniv.ac.in")),
    (" library", "Central Library", ("lib.dauniv.ac.in", "edu.dauniv.ac.in")),
    ("student welfare", "Dean of Student Welfare", ("dsw.dauniv.ac.in",)),
    ("placement", "Centralised Placement Cell", ("cpc.dauniv.ac.in",)),
)


def understand_question(question: str) -> dict:
    lowered = f" {(question or '').lower()} "
    found: list[tuple[str, tuple[str, ...]]] = []
    for needle, name, hosts in DEPARTMENTS:
        if needle in lowered and all(name != existing[0] for existing in found):
            found.append((name, hosts))
    intent = "general"
    if any(word in lowered for word in (" where ", " located", " address")):
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
    if not hosts or understood["intent"] not in {"location", "courses", "faculty", "services"}:
        return sources, "University-wide indexed pages were kept."
    names = [name.lower() for name in understood["departments"]]
    matched = []
    for source in sources:
        url = (source.get("source_url") or "").lower()
        label = f"{source.get('department') or ''} {source.get('document_title') or ''}".lower()
        if any(host in url for host in hosts) or any(name in label for name in names):
            matched.append(source)
    if not matched:
        return sources, (
            f"No retrieved passage came from {', '.join(understood['departments'])}. "
            "University-wide evidence was kept instead of guessing."
        )
    if understood["intent"] == "location":
        text = " ".join((source.get("excerpt") or "") for source in matched).lower()
        if not any(word in text for word in ("takshila", "nalanda", "khandwa", "indore", "address", "campus")):
            return sources, "The department pages did not state an address, so other official evidence was kept."
    return matched, f"Evidence limited to {', '.join(understood['departments'])}."
