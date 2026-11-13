"""PDF validation, indexing, and grounded answers."""

from tests.conftest import auth_header, pdf_bytes


def _admin(client):
    student = client.post(
        "/api/auth/register",
        json={"full_name": "Meera Nair", "email": "meera@example.com", "password": "Student@12345"},
    ).json()
    # Promote the only user through the database so the test does not need a seed account.
    from app.core.config import get_settings
    from app.database.session import get_session_factory
    from app.models.entities import User

    get_settings.cache_clear()
    db = get_session_factory()()
    user = db.query(User).filter(User.email == "meera@example.com").one()
    user.role = "admin"
    db.commit()
    db.close()
    token = client.post(
        "/api/auth/login",
        json={"email": "meera@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    return token, student["user"]["id"]


def test_rejects_non_pdf(client):
    token, _user_id = _admin(client)
    response = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Notes", "category": "Other"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_rejects_fake_pdf_bytes(client):
    token, _user_id = _admin(client)
    response = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Notes", "category": "Other"},
        files={"file": ("notes.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_empty_pdf_needs_ocr(client):
    token, _user_id = _admin(client)
    response = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Scan", "category": "Other"},
        files={"file": ("scan.pdf", pdf_bytes("   "), "application/pdf")},
    )
    # A page that only contains spaces extracts too little text.
    assert response.status_code == 201
    assert response.json()["status"] == "needs_ocr"
    assert response.json()["chunk_count"] == 0


def test_index_and_answer_with_citation(client):
    token, _user_id = _admin(client)
    text = (
        "Minimum attendance for examinations is 75 percent. "
        "The minimum attendance requirement for examinations is 75 percent in each course. "
        "Students need this minimum attendance before examinations."
    )
    uploaded = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Attendance Policy", "category": "Attendance"},
        files={"file": ("attendance.pdf", pdf_bytes(text), "application/pdf")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "processed"
    assert uploaded.json()["chunk_count"] >= 1

    session = client.post("/api/chat/sessions", headers=auth_header(token)).json()
    answer = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "What is the minimum attendance required for examinations?"},
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["metadata"]["answer_mode"] == "retrieval_only"
    assert body["sources"]
    assert body["sources"][0]["document_title"] == "Attendance Policy"
    assert body["sources"][0]["page_number"] == 1
    assert "75" in body["content"] or "75" in body["sources"][0]["excerpt"]


def test_unknown_question_is_not_invented(client):
    token, _user_id = _admin(client)
    text = "Quiet hours in the hostel are from 22:00 to 06:00. Visitors leave the lobby at 19:00."
    client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Hostel Rules", "category": "Hostel"},
        files={"file": ("hostel.pdf", pdf_bytes(text), "application/pdf")},
    )
    session = client.post("/api/chat/sessions", headers=auth_header(token)).json()
    answer = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "What is the library overdue fine per day?"},
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["metadata"]["answer_mode"] == "insufficient_context"
    assert body["sources"] == []
    assert "do not contain enough information" in body["content"].lower()


def test_student_cannot_upload(client):
    token = client.post(
        "/api/auth/register",
        json={"full_name": "Meera Nair", "email": "meera@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    response = client.post(
        "/api/documents",
        headers=auth_header(token),
        data={"title": "Notes", "category": "Other"},
        files={"file": ("notes.pdf", pdf_bytes("A long enough attendance sentence for indexing."), "application/pdf")},
    )
    assert response.status_code == 403
