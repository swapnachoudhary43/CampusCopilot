"""Complaints, events, classification, and analytics."""

from datetime import timedelta

from app.utils.time import utcnow
from tests.conftest import auth_header


def register(client, email, name="Meera Nair"):
    response = client.post(
        "/api/auth/register",
        json={"full_name": name, "email": email, "password": "Student@12345", "department": "AI and Data Science"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def promote(email, role):
    from app.database.session import get_session_factory
    from app.models.entities import User

    db = get_session_factory()()
    user = db.query(User).filter(User.email == email).one()
    user.role = role
    db.commit()
    db.close()


def test_complaint_create_and_privacy(client):
    student = register(client, "meera@example.com")
    other = register(client, "arjun@example.com", "Arjun Das")
    created = client.post(
        "/api/complaints",
        headers=auth_header(student),
        json={
            "title": "Broken classroom projector",
            "description": "The projector in lecture hall LH-3 does not switch on.",
            "location": "Lecture hall LH-3",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "submitted"
    assert body["priority_method"] == "rule_based"
    assert body["suggested_priority"] in {"low", "medium", "high"}
    hidden = client.get(f"/api/complaints/{body['id']}", headers=auth_header(other))
    assert hidden.status_code == 404


def test_faculty_updates_only_assigned_complaint(client):
    student = register(client, "meera@example.com")
    register(client, "rahul@example.com", "Rahul Iyer")
    promote("rahul@example.com", "faculty")
    faculty = client.post(
        "/api/auth/login",
        json={"email": "rahul@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    register(client, "asha@example.com", "Asha Menon")
    promote("asha@example.com", "admin")
    admin = client.post(
        "/api/auth/login",
        json={"email": "asha@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    complaint = client.post(
        "/api/complaints",
        headers=auth_header(student),
        json={"title": "Cold geyser in hostel", "description": "The geyser in hostel room 214 is not heating water."},
    ).json()
    before_assignment = client.patch(
        f"/api/complaints/{complaint['id']}",
        headers=auth_header(faculty),
        json={"status": "in_progress"},
    )
    assert before_assignment.status_code == 404
    staff = client.get("/api/users/staff", headers=auth_header(admin)).json()
    faculty_id = next(person["id"] for person in staff if person["email"] == "rahul@example.com")
    assigned = client.patch(
        f"/api/complaints/{complaint['id']}",
        headers=auth_header(admin),
        json={"assigned_to": faculty_id, "department": "Hostel"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"
    moved = client.patch(
        f"/api/complaints/{complaint['id']}",
        headers=auth_header(faculty),
        json={"status": "in_progress"},
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "in_progress"
    resolved = client.patch(
        f"/api/complaints/{complaint['id']}",
        headers=auth_header(faculty),
        json={"status": "resolved", "resolution_remarks": "The geyser heating coil was replaced."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_event_duplicate_and_capacity(client):
    student = register(client, "meera@example.com")
    other = register(client, "arjun@example.com", "Arjun Das")
    register(client, "asha@example.com", "Asha Menon")
    promote("asha@example.com", "admin")
    admin = client.post(
        "/api/auth/login",
        json={"email": "asha@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    start = utcnow() + timedelta(days=3)
    end = start + timedelta(hours=2)
    event = client.post(
        "/api/events",
        headers=auth_header(admin),
        json={
            "title": "AI Workshop on Campus Assistants",
            "description": "A short sample workshop used by the automated test.",
            "venue": "Seminar Hall 2",
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "capacity": 1,
        },
    )
    assert event.status_code == 201
    event_id = event.json()["id"]
    first = client.post(f"/api/events/{event_id}/register", headers=auth_header(student))
    assert first.status_code == 200
    duplicate = client.post(f"/api/events/{event_id}/register", headers=auth_header(student))
    assert duplicate.status_code == 409
    full = client.post(f"/api/events/{event_id}/register", headers=auth_header(other))
    assert full.status_code == 409


def test_agent_complaint_waits_for_confirmation(client):
    token = register(client, "meera@example.com")
    session = client.post("/api/agent/sessions", headers=auth_header(token)).json()
    draft = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "I want to complain about a broken projector in classroom LH-2."},
    )
    assert draft.status_code == 200
    assert draft.json()["needs_confirmation"] is True
    assert client.get("/api/complaints", headers=auth_header(token)).json() == []
    saved = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "YES"},
    )
    assert saved.status_code == 200
    complaints = client.get("/api/complaints", headers=auth_header(token)).json()
    assert len(complaints) == 1
    assert complaints[0]["priority_method"] == "rule_based"


def test_agent_cancel_does_not_save(client):
    token = register(client, "meera@example.com")
    session = client.post("/api/agent/sessions", headers=auth_header(token)).json()
    client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "I want to complain about a broken fan in classroom A-110."},
    )
    cancelled = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(token),
        json={"content": "NO"},
    )
    assert cancelled.status_code == 200
    assert client.get("/api/complaints", headers=auth_header(token)).json() == []


def test_agent_event_registration(client):
    student = register(client, "meera@example.com")
    register(client, "asha@example.com", "Asha Menon")
    promote("asha@example.com", "admin")
    admin = client.post(
        "/api/auth/login",
        json={"email": "asha@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    start = utcnow() + timedelta(days=5)
    client.post(
        "/api/events",
        headers=auth_header(admin),
        json={
            "title": "AI Workshop on Campus Assistants",
            "description": "A short sample workshop used by the automated test.",
            "venue": "Seminar Hall 2",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "capacity": 20,
        },
    )
    session = client.post("/api/agent/sessions", headers=auth_header(student)).json()
    asked = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(student),
        json={"content": "Show me upcoming events and register me for the AI workshop."},
    )
    assert asked.json()["needs_confirmation"] is True
    confirmed = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=auth_header(student),
        json={"content": "yes"},
    )
    assert "registered" in confirmed.json()["content"].lower()
    mine = client.get("/api/events/me/registrations", headers=auth_header(student)).json()
    assert len(mine) == 1


def test_notice_summary_is_labelled(client):
    register(client, "asha@example.com", "Asha Menon")
    promote("asha@example.com", "admin")
    admin = client.post(
        "/api/auth/login",
        json={"email": "asha@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    created = client.post(
        "/api/notices",
        headers=auth_header(admin),
        json={
            "title": "Scholarship reminder",
            "audience": "students",
            "body": "All students must submit scholarship applications by 20 November 2026 at Admin Block Room 12.",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["summary_method"] == "extractive_fallback"
    assert body["extraction_disclaimer"]
    assert any(item["verified"] is False for item in body["deadlines"])


def test_analytics_uses_database_counts(client):
    student = register(client, "meera@example.com")
    register(client, "asha@example.com", "Asha Menon")
    promote("asha@example.com", "admin")
    denied = client.get("/api/analytics/overview", headers=auth_header(student))
    assert denied.status_code == 403
    client.post(
        "/api/complaints",
        headers=auth_header(student),
        json={"title": "Overflowing bins", "description": "Garbage bins near the bus stop are overflowing onto the footpath."},
    )
    admin = client.post(
        "/api/auth/login",
        json={"email": "asha@example.com", "password": "Student@12345"},
    ).json()["access_token"]
    overview = client.get("/api/analytics/overview", headers=auth_header(admin))
    assert overview.status_code == 200
    body = overview.json()
    assert body["total_users"] == 2
    assert body["total_complaints"] == 1
    assert body["notices"] == 0
