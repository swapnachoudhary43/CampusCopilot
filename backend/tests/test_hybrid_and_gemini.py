"""Hybrid retrieval helpers, Gemini fallback, and a duplicate upload."""

from types import SimpleNamespace

from app.services.rag.generator import GeminiError
from app.services.rag.lexical import bm25_ranks
from app.services.rag.pipeline import _group_pages, _search_query, requirement_numbers
from tests.conftest import auth_header, pdf_bytes


def test_bm25_prefers_the_chunk_with_the_exact_words():
    documents = [
        (1, "Core committee of the centralized placement cell coordinator"),
        (2, "1050 students placed 1400 total offers 6.5 LPA average CTC"),
    ]
    ranks = bm25_ranks(documents, "placement rate of CPC students placed")
    assert ranks[0][0] == 2


def test_short_new_topic_is_not_glued_to_the_previous_question():
    history = [{"role": "user", "content": "What attendance does Ordinance 6 require?"}]
    assert _search_query("Fee?", history) == "Fee?"


def test_short_follow_fragment_keeps_the_previous_question():
    history = [{"role": "user", "content": "What attendance does Ordinance 6 require?"}]
    assert "Ordinance 6" in _search_query("and practicals?", history)


def test_gemini_failure_returns_evidence_without_the_provider_error(client, monkeypatch):
    token = client.post(
        "/api/auth/register",
        json={"full_name": "Meera Nair", "email": "meera-gem@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    from app.core.config import get_settings
    from app.database.session import get_session_factory
    from app.models.entities import User

    get_settings.cache_clear()
    db = get_session_factory()()
    user = db.query(User).filter(User.email == "meera-gem@example.com").one()
    user.role = "admin"
    db.commit()
    db.close()
    token = client.post(
        "/api/auth/login",
        json={"email": "meera-gem@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Attendance Policy", "category": "Attendance"},
        files={
            "file": (
                "attendance.pdf",
                pdf_bytes(
                    "Minimum attendance for examinations is 75 percent. "
                    "The minimum attendance requirement for examinations is 75 percent in each course. "
                    "Students need this minimum attendance before examinations."
                ),
                "application/pdf",
            )
        },
    )

    def fail(_prompt):
        raise GeminiError("The AI generation service is temporarily unavailable. The verified campus evidence is shown below.")

    monkeypatch.setattr("app.services.rag.pipeline.generate_with_gemini", fail)
    monkeypatch.setattr("app.core.config.Settings.resolved_llm_mode", lambda self: "gemini")
    session = client.post("/api/chat/sessions", headers=auth_header(token)).json()
    answer = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "What is the minimum attendance required for examinations?"},
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["metadata"]["answer_mode"] == "llm_unavailable"
    assert "503" not in body["content"]
    assert "temporarily unavailable" in body["content"]
    assert body["sources"]


def test_duplicate_pdf_is_rejected(client):
    from app.core.config import get_settings
    from app.database.session import get_session_factory
    from app.models.entities import User

    client.post(
        "/api/auth/register",
        json={"full_name": "Meera Nair", "email": "meera-dup@example.com", "password": "Student@12345"},
    )
    get_settings.cache_clear()
    db = get_session_factory()()
    user = db.query(User).filter(User.email == "meera-dup@example.com").one()
    user.role = "admin"
    db.commit()
    db.close()
    token = client.post(
        "/api/auth/login",
        json={"email": "meera-dup@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    payload = pdf_bytes("Hostel quiet hours are posted on the notice board for residents.")
    first = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Hostel notice", "category": "Hostel"},
        files={"file": ("hostel.pdf", payload, "application/pdf")},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Hostel notice copy", "category": "Hostel"},
        files={"file": ("hostel-copy.pdf", payload, "application/pdf")},
    )
    assert second.status_code == 409


def test_spelled_and_digit_attendance_minimums_are_read():
    assert requirement_numbers(
        "attendance at least seventy five percent of lectures and practical separately"
    ) == {"75"}
    assert "75" in requirement_numbers("candidates who have attendance at least 75 percent both of the lectures")
    assert "85" in requirement_numbers("Faculty of Engineering attendance at least eighty five percent of lectures")


def test_named_ordinance_page_with_the_figure_outranks_a_nearby_page():
    def part(doc_id, page, index, text, fusion, title):
        chunk = SimpleNamespace(document_id=doc_id, page_number=page, chunk_index=index, text=text, id=index)
        return {
            "_chunk": chunk,
            "document_id": doc_id,
            "document_title": title,
            "fusion_score": fusion,
            "semantic_score": 0.5,
            "lexical_score": 4.0,
            "score": 0.5,
            "retrieval_method": "hybrid",
            "source_url": None,
            "publication_date": None,
            "provenance": "test",
            "page_number": page,
            "excerpt": "",
        }

    pages = _group_pages(
        [
            part(2, 2, 1, "the minimum attendance requirement shall apply equally", 0.9, "Ordinance No. 6 — Examinations"),
            part(
                2,
                1,
                2,
                ("definition " * 80) + "attendance at least seventy five percent of lectures and practical separately",
                0.2,
                "Ordinance No. 6 — Examinations",
            ),
            part(14, 8, 3, "Equivalent Percentage = CGPA x10 The percentage will be rounded", 0.8, "Ordinance No. 14"),
        ],
        "What attendance percentage is required under Ordinance No. 6?",
    )
    assert pages[0]["page_number"] == 1
    assert "seventy five percent" in pages[0]["excerpt"]
    assert all("Ordinance No. 14" not in page["document_title"] for page in pages)
