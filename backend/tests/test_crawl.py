"""Official-site crawl, without calling the public internet."""

import httpx

from app.services.crawl.allowlist import host_allowed
from app.services.crawl.extract import extract_html
from app.services.crawl.robots import disallowed_prefixes, path_allowed
from app.services.rag.lexical import bm25_ranks
from app.services.rag.pipeline import _search_query, library_hours_gap, prefer_location_sources, schedule_answer, specific_term_overlap
from app.services.rag.workflow import focus_department_sources, understand_question


def test_allowlist_rejects_unrelated_hosts():
    assert host_allowed("https://www.dauniv.ac.in/library")
    assert host_allowed("https://dsf.dauniv.ac.in/")
    assert host_allowed("https://www.ietdavv.edu.in/")
    assert host_allowed("https://iips.edu.in/courses.php")
    assert host_allowed("https://www.cdoedavv.ac.in/")
    assert not host_allowed("https://example.com/library")
    assert not host_allowed("https://www.ugc.ac.in/")


def test_robots_disallow_is_honoured():
    prefixes = disallowed_prefixes("User-agent: *\nDisallow: /private\n")
    assert path_allowed("/library", prefixes)
    assert not path_allowed("/private", prefixes)


def test_html_extraction_keeps_the_heading_and_link():
    title, text, links = extract_html(
        "<html><title>Central Library</title><h1>Hours</h1><p>Library working hours are 10:00 to 18:00.</p>"
        "<a href='/contact'>Contact</a></html>",
        "https://www.dauniv.ac.in/library",
    )
    assert title == "Central Library"
    assert "Library working hours" in text
    assert "Heading:" in text
    assert links == ["https://www.dauniv.ac.in/contact"]


def test_library_hours_phrase_outranks_an_unrelated_page():
    ranks = bm25_ranks(
        [
            (1, "Ordinance examination fee percentage"),
            (2, "Central Library working hours opening hours are 10:00 to 18:00"),
        ],
        "What are the library timings? library working hours opening hours",
    )
    assert ranks[0][0] == 2


def test_pronoun_follow_up_keeps_the_library_topic():
    history = [{"role": "user", "content": "Tell me about the central library"}]
    assert "central library" in _search_query("What are its timings?", history).lower()


def test_a_named_school_is_not_answered_from_another_institute():
    understood = understand_question("Where is the School of Data Science and Forecasting located?")
    assert understood["departments"] == ["School of Data Science and Forecasting"]
    sources, note = focus_department_sources(
        "Where is the School of Data Science and Forecasting located?",
        [
            {"source_url": "https://iips.edu.in/about.php", "excerpt": "IIPS is at a different campus address in Indore."},
            {"source_url": "https://dsf.dauniv.ac.in/about.php", "excerpt": "Address: Takshila Campus, Indore."},
        ],
        understood,
    )
    assert len(sources) == 1
    assert "dsf.dauniv.ac.in" in sources[0]["source_url"]
    assert "School of Data Science" in note


def test_anything_and_campus_do_not_count_as_a_subject_match():
    assert not specific_term_overlap(
        "Is anything happening on campus tomorrow?",
        "unless there is anything repugnant in the subject or context on campus",
    )
    assert specific_term_overlap(
        "What attendance percentage does Ordinance 6 require?",
        "attendance at least seventy five percent of lectures",
    )


def test_tomorrow_uses_the_event_schedule_and_not_an_ordinance(client):
    from datetime import timedelta

    from app.database.session import get_session_factory
    from app.models.entities import Event
    from app.utils.time import utcnow

    db = get_session_factory()()
    db.add(
        Event(
            title="DEMO: Saturday workshop",
            description="DEMO DATA. Not a DAVV event.",
            venue="DEMO venue",
            starts_at=utcnow() + timedelta(days=9),
            ends_at=utcnow() + timedelta(days=9, hours=2),
            capacity=10,
            is_demo=True,
        )
    )
    db.commit()
    answer = schedule_answer(db, "Is anything happening on campus tomorrow?")
    db.close()
    assert answer is not None
    assert "Nothing in the campus event schedule" in answer
    assert "Ordinance" not in answer
    assert "DEMO: Saturday workshop" in answer


def test_a_library_mention_is_not_treated_as_opening_hours():
    message = library_hours_gap(
        "What are the library timings?",
        [{"document_title": "Admission guide", "excerpt": "Please visit the library and other places."}],
    )
    assert message is not None
    assert "will not guess" in message


def test_a_timetable_is_not_used_as_an_address_when_an_address_exists():
    sources = prefer_location_sources(
        "Where is the School of Data Science and Forecasting located?",
        [
            {"document_title": "Class timetable", "excerpt": "Monday period 1 room 12 timetable"},
            {"document_title": "Department contact", "excerpt": "Address: Takshila Campus, Indore 452001"},
        ],
    )
    assert len(sources) == 1
    assert "Takshila" in sources[0]["excerpt"]


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
    if path == "/":
        return httpx.Response(
            200,
            text=(
                "<html><title>Devi Ahilya Vishwavidyalaya</title>"
                "<p>Address: Takshila Campus, Indore.</p>"
                "<a href='/library'>Library</a>"
                "<a href='/private'>Hidden</a>"
                "<a href='https://example.com/other'>Other</a></html>"
            ),
        )
    if path == "/library":
        return httpx.Response(
            200,
            text="<html><title>Central Library</title><p>Library working hours are 10:00 AM to 6:00 PM.</p></html>",
        )
    if path == "/missing":
        return httpx.Response(404, text="missing")
    return httpx.Response(200, text="<html><title>Unexpected</title><p>This page should not be stored.</p></html>")


def test_crawl_indexes_official_pages_and_skips_blocked_ones(client):
    from app.database.session import get_session_factory
    from app.models.entities import CrawlRecord, Document
    from app.services.crawl.runner import crawl_official_sites
    from app.services.rag.pipeline import answer_question

    db = get_session_factory()()
    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport, follow_redirects=True) as http:
        first = crawl_official_sites(
            db,
            client=http,
            seeds=["https://www.dauniv.ac.in/", "https://www.dauniv.ac.in/missing"],
            max_pages=5,
            max_pdfs=0,
            pause_seconds=0,
        )
        second = crawl_official_sites(
            db,
            client=http,
            seeds=["https://www.dauniv.ac.in/"],
            max_pages=5,
            max_pdfs=0,
            pause_seconds=0,
        )
    assert first["indexed"] >= 2
    assert second["unchanged"] >= 1
    statuses = {row.url: row.status for row in db.query(CrawlRecord).all()}
    assert statuses["https://www.dauniv.ac.in/private"] == "skipped_robots"
    assert statuses["https://example.com/other"] == "skipped_off_allowlist"
    assert statuses["https://www.dauniv.ac.in/missing"] == "failed"
    titles = [row.title for row in db.query(Document).all()]
    assert any("Library" in title for title in titles)
    answer = answer_question(db, "What are the library timings?")
    db.close()
    assert answer["sources"]
    assert any("10:00" in source["excerpt"] for source in answer["sources"])
    assert answer["sources"][0]["source_url"].startswith("https://www.dauniv.ac.in/")
