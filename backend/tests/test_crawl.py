"""Official-site crawl, without calling the public internet."""

import httpx

from app.services.crawl.allowlist import SEED_URLS, department_for, host_allowed
from app.services.crawl.extract import extract_html, looks_like_script_shell
from app.services.crawl.robots import disallowed_prefixes, path_allowed
from app.services.rag.lexical import bm25_ranks
from app.services.rag.pipeline import _merge_sources, _notice_excerpt, _search_query, library_hours_gap, prefer_location_sources, schedule_answer, specific_term_overlap
from app.services.rag.workflow import focus_department_sources, is_notice_question, understand_question


def test_allowlist_rejects_unrelated_hosts():
    assert host_allowed("https://www.dauniv.ac.in/library")
    assert host_allowed("https://dsf.dauniv.ac.in/")
    assert host_allowed("https://www.ietdavv.edu.in/")
    assert host_allowed("https://iips.edu.in/courses.php")
    assert host_allowed("https://www.cdoedavv.ac.in/")
    assert not host_allowed("https://example.com/library")
    assert not host_allowed("https://www.ugc.ac.in/")


def test_official_seed_urls_cover_requested_sites_and_latest_pages():
    required = {
        "https://www.dauniv.ac.in/",
        "https://www.dauniv.ac.in/admission",
        "https://www.dauniv.ac.in/exam-notice",
        "https://www.dauniv.ac.in/web2027",
        "https://edu.dauniv.ac.in/academics.php",
        "https://edu.dauniv.ac.in/Library.php",
        "https://www.cdoedavv.ac.in/notices",
        "https://iconnect.ietdavv.edu.in/",
        "https://iips.edu.in/news_and_announcements.php",
        "https://iips.edu.in/academic_calendar.php",
        "https://dsf.dauniv.ac.in/SDSF_News/news.php?category=all",
    }
    assert required.issubset(SEED_URLS)
    assert department_for("https://edu.dauniv.ac.in/Library.php") == "School of Education"


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


def test_script_shell_for_i_connect_is_not_searchable_content():
    assert looks_like_script_shell(
        "<html><body>Loading services… <form>Welcome back</form></body></html>",
        "iConnect Welcome to IET-DAVV Loading services Welcome back",
    )


def test_recrawling_script_shell_disables_previous_stale_index(client):
    from app.database.session import get_session_factory
    from app.models.entities import DocumentChunk
    from app.services.crawl.runner import _store_html
    from app.services.rag.ingest import upsert_text_source

    url = "https://iconnect.ietdavv.edu.in/"
    db = get_session_factory()()
    document, _outcome = upsert_text_source(
        db,
        title="iConnect",
        category="Other",
        text="Old placeholder service content that should not remain searchable.",
        source_url=url,
        provenance="official_webpage",
        document_type="official_webpage",
        rebuild=False,
    )
    response = httpx.Response(
        200,
        text="<html><title>iConnect</title><body>Loading services… <form>Welcome back</form></body></html>",
        request=httpx.Request("GET", url),
    )

    _store_html(db, response, url, None)

    db.refresh(document)
    assert document.status == "needs_render"
    assert document.chunk_count == 0
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count() == 0
    db.close()


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


def test_general_question_about_named_department_is_scoped_to_its_website():
    question = "What are the latest notices of IIPS?"
    understood = understand_question(question)
    sources, _note = focus_department_sources(
        question,
        [
            {"source_url": "https://iips.edu.in/news_and_announcements.php", "department": "International Institute of Professional Studies"},
            {"source_url": "https://dsf.dauniv.ac.in/SDSF_News/news.php", "department": "School of Data Science and Forecasting"},
        ],
        understood,
    )
    assert len(sources) == 1
    assert "iips.edu.in" in sources[0]["source_url"]


def test_school_attendance_question_can_use_university_ordinance_not_a_calendar(client):
    from app.database.session import get_session_factory
    from app.services.rag.ingest import rebuild_from_database, upsert_text_source
    from app.services.rag.pipeline import answer_question

    db = get_session_factory()()
    upsert_text_source(
        db,
        title="School of Data Science and Forecasting — About",
        category="Other",
        text="The School of Data Science and Forecasting offers undergraduate and postgraduate programmes.",
        source_url="https://dsf.dauniv.ac.in/about.php",
        provenance="official_webpage",
        document_type="official_webpage",
        department="School of Data Science and Forecasting",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="Ordinance No. 6 — Examinations (General)",
        category="Examinations",
        text=(
            "For faculties other than Medicine, Ayurveda, and Engineering, attendance at least "
            "seventy five percent of lectures and practicals separately. Faculty of Engineering "
            "attendance at least eighty five percent of lectures and practical work separately."
        ),
        source_url="https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-6.pdf",
        provenance="official_pdf",
        document_type="official_pdf",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="05.10.2026 Revised Academic Calendar",
        category="Calendar",
        text="Students must ensure at least 75% attendance before examinations.",
        source_url="https://notices.ietdavv.edu.in/calendar.pdf",
        provenance="official_pdf",
        document_type="official_pdf",
        rebuild=False,
    )
    rebuild_from_database(db)
    result = answer_question(db, "attendance criteria of School of Data Science and Forecasting")
    db.close()
    assert result["sources"]
    assert any("Ordinance No. 6" in source["document_title"] for source in result["sources"])
    assert all("Academic Calendar" not in source["document_title"] for source in result["sources"])
    assert "75% in lectures and practicals separately" in result["answer"]
    assert "85%" not in result["answer"]


def test_notice_question_prefers_notice_page_to_same_department_keyword_hit():
    question = "What are the latest notices of IIPS?"
    understood = understand_question(question)
    assert understood["intent"] == "notices"
    sources = _merge_sources(
        [[
            {
                "document_id": 1,
                "page_number": 1,
                "source_url": "https://iips.edu.in/placement.php",
                "document_title": "Placements @ IIPS",
                "excerpt": "Information about companies and placements.",
                "fusion_score": 0.9,
            },
            {
                "document_id": 2,
                "page_number": 1,
                "source_url": "https://iips.edu.in/news_and_announcements.php",
                "document_title": "News and Announcements — IIPS",
                "excerpt": "Admission announcement, dated August 2026.",
                "fusion_score": 0.1,
            },
        ]],
        limit=1,
        query=question,
    )
    assert sources[0]["source_url"] == "https://iips.edu.in/news_and_announcements.php"


def test_notice_intent_tolerates_common_query_misspellings():
    assert understand_question("give the lastest notics of sdsf and iips")["intent"] == "notices"
    assert is_notice_question("latest ntois of school of data science forrcasting")


def test_latest_notice_sources_read_the_full_official_notice_pages(client):
    from app.database.session import get_session_factory
    from app.services.rag.ingest import rebuild_from_database, upsert_text_source
    from app.services.rag.pipeline import answer_question

    db = get_session_factory()()
    upsert_text_source(
        db,
        title="SDSF Chronicle — News",
        category="Other",
        text=(
            "SDSF Chronicle. Issued on 02/11/26. Recent Updates. "
            "Final Examination Time Table updated (Nov-Dec 2026). "
            "Workshop conducted 26-31 Oct 2026."
        ),
        source_url="https://dsf.dauniv.ac.in/SDSF_News/news.php",
        provenance="official_webpage",
        document_type="official_webpage",
        department="School of Data Science and Forecasting",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="Academics | SDSF",
        category="Other",
        text=(
            "Heading: Official Notices & Circulars. NEW: Final Examination Time Table "
            "(Semester End Examination Nov-Dec 2026) UPDATED. "
            "Notice Regarding Final Ph.D. Viva Voce dated 24.08.2026."
        ),
        source_url="https://dsf.dauniv.ac.in/academics.php",
        provenance="official_webpage",
        document_type="official_webpage",
        department="School of Data Science and Forecasting",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="News and Announcements | IIPS",
        category="Other",
        text=(
            "Heading: News and Announcements. B.Com. Enrollment List 2018. "
            "MBA Enrollment List 2018. Admission - Fees Structure - Admission CUET-2026."
        ),
        source_url="https://iips.edu.in/news_and_announcements.php",
        provenance="official_webpage",
        document_type="official_webpage",
        department="International Institute of Professional Studies",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="Home | IIPS",
        category="Other",
        text=(
            "News and Announcements - Exam Form Notice 2026 - "
            "ATKT Exam Form Notice 2026 - Fee Notice Session Jul-Dec 2026."
        ),
        source_url="https://iips.edu.in/",
        provenance="official_webpage",
        document_type="official_webpage",
        department="International Institute of Professional Studies",
        rebuild=False,
    )
    rebuild_from_database(db)

    result = answer_question(db, "give the lastest notics of sdsf and iips")
    sources = result["sources"]
    db.close()

    assert any("dsf.dauniv.ac.in" in source["source_url"] for source in sources)
    assert any("iips.edu.in" in source["source_url"] for source in sources)
    assert "dsf.dauniv.ac.in" in sources[0]["source_url"]
    assert "iips.edu.in" in sources[1]["source_url"]
    sdsf_sources = [source for source in sources if "dsf.dauniv.ac.in" in source["source_url"]]
    iips_sources = [source for source in sources if "iips.edu.in" in source["source_url"]]
    assert any("Final Examination Time Table" in source["excerpt"] for source in sdsf_sources)
    assert any("02/11/26" in source["excerpt"] for source in sdsf_sources)
    assert "Exam Form Notice 2026" in iips_sources[0]["excerpt"]
    assert "Enrollment List 2018" in iips_sources[1]["excerpt"]
    assert "CUET-2026" not in iips_sources[1]["excerpt"]
    assert "Exam Form Notice 2026" in result["answer"]
    assert len(result["answer"].split()) < 120


def test_notice_excerpt_does_not_replace_item_dates_with_footer_dates():
    excerpt = _notice_excerpt(
        "Heading: News and Announcements - Enrollment List 2018. "
        "Admission - Fees Structure - Admission CUET-2026. © 1990-2026."
    )
    assert "Enrollment List 2018" in excerpt
    assert "CUET-2026" not in excerpt
    assert "1990" not in excerpt


def test_named_school_location_prefers_address_page_over_timetable(client):
    from app.database.session import get_session_factory
    from app.services.rag.ingest import rebuild_from_database, upsert_text_source
    from app.services.rag.pipeline import answer_question

    db = get_session_factory()()
    upsert_text_source(
        db,
        title="M.Tech class timetable",
        category="Other",
        text=(
            "M.Tech timetable for School of Data Science and Forecasting. "
            "Classes are held at Takshila Campus, Indore, on the dates listed below."
        ),
        source_url="https://dsf.dauniv.ac.in/timetable",
        provenance="official_webpage",
        document_type="official_webpage",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="School of Data Science and Forecasting - About",
        category="Other",
        text=(
            "School of Data Science and Forecasting, DAVV. "
            "Address: Takshila Campus, Indore 452001, Madhya Pradesh, India."
        ),
        source_url="https://dsf.dauniv.ac.in/about.php",
        provenance="official_webpage",
        document_type="official_webpage",
        rebuild=False,
    )
    rebuild_from_database(db)
    answer = answer_question(db, "Where is the School of Data Science and Forecasting located?")
    db.close()
    assert answer["sources"]
    assert "timetable" not in answer["sources"][0]["document_title"].lower()
    assert "Takshila" in answer["sources"][0]["excerpt"]


def test_department_exam_query_returns_the_final_schedule_not_class_timetables(client):
    from app.database.session import get_session_factory
    from app.services.rag.ingest import rebuild_from_database, upsert_text_source
    from app.services.rag.pipeline import answer_question

    db = get_session_factory()()
    upsert_text_source(
        db,
        title="Academics | SDSF",
        category="Examinations",
        text=(
            "School of Data Science and Forecasting. Exam Time Table Nov-Dec 2026 "
            "for III, V, VII and IX Semester. Semester End Examination Schedule, "
            "November and December 2026. Exam time: 11:00 AM to 2:00 PM "
            "VII Semester Revised 26-11-2026 DS6A-401 Data Visualization. "
            "M.Tech Dual Degree Artificial Intelligence and Data Science. IX Semester Revised. "
            "26-11-2026 Thursday DS6A-501 Multivariate Analytics. "
            "28-11-2026 Saturday DS6A-503 Agentic AI. "
            "02-12-2026 Wednesday DS6A-509 Project Report Writing. "
            "04-12-2026 Friday DS6A-511 Natural Language Processing. "
            "07-12-2026 Monday DS6A-505 Artificial Intelligence Foundations and Algorithms. "
            "09-12-2026 Wednesday DS6A-507 High Performance Computing."
        ),
        source_url="https://dsf.dauniv.ac.in/academics.php",
        provenance="official_webpage",
        document_type="official_webpage",
        department="School of Data Science and Forecasting",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="M.Tech class timetable, Ninth Semester",
        category="Calendar",
        text=(
            "School of Data Science and Forecasting. Ninth Semester class timetable. "
            "Classes are scheduled Monday to Saturday in room B-006."
        ),
        source_url="https://dsf.dauniv.ac.in/time_tables/AIDS.pdf",
        provenance="official_webpage",
        document_type="official_webpage",
        department="School of Data Science and Forecasting",
        rebuild=False,
    )
    upsert_text_source(
        db,
        title="Ordinance No. 6 — Examinations (General)",
        category="Examinations",
        text=(
            "The university examination ordinance covers examination rules and candidate eligibility."
        ),
        source_url="https://www.dauniv.ac.in/frontassets/ordinance/Ordinance-6.pdf",
        provenance="official_pdf",
        document_type="official_pdf",
        rebuild=False,
    )
    rebuild_from_database(db)
    answer = answer_question(
        db,
        "give me the 9th semester final examination time table of School of Data Science and Forecasting",
    )
    db.close()
    assert answer["sources"]
    assert answer["sources"][0]["source_url"] == "https://dsf.dauniv.ac.in/academics.php"
    assert "26-11-2026" in answer["sources"][0]["excerpt"]
    assert "DS6A-503 Agentic AI" in answer["sources"][0]["excerpt"]
    assert "DS6A-401 Data Visualization" not in answer["sources"][0]["excerpt"]
    assert "11:00 AM to 2:00 PM" in answer["sources"][0]["excerpt"]
    assert all("class timetable" not in source["document_title"].lower() for source in answer["sources"])
    assert all("Ordinance No. 6" not in source["document_title"] for source in answer["sources"])


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
