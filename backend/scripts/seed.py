"""Load public DAVV PDFs and a small labelled demonstration set.

Official PDFs come from data/official_documents/davv/manifest.json.
Accounts, complaints, events, and the placeholder notice are DEMO DATA.
They are not DAVV records. Run train_model.py first so complaints receive
a category prediction. The script can be run more than once.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.database.session import get_session_factory, init_db  # noqa: E402
from app.models.entities import Complaint, ComplaintHistory, Document, Event, EventRegistration, Notice, User  # noqa: E402
from app.services.complaints import create_complaint  # noqa: E402
from app.services.notices import dumps_result, summarise_notice  # noqa: E402
from app.services.rag.ingest import delete_document, store_pdf  # noqa: E402
from app.services.rag.pipeline import answer_question  # noqa: E402
from app.utils.time import utcnow  # noqa: E402

FICTIONAL_FILES = {
    "01_academic_regulations.pdf",
    "02_attendance_policy.pdf",
    "03_examination_schedule.pdf",
    "04_fee_structure.pdf",
    "05_hostel_rules.pdf",
    "06_scholarship_circular.pdf",
    "07_academic_calendar.pdf",
    "08_ai21_syllabus.pdf",
}
REMOVED_NOTICES = {
    "Scholarship applications for the sample academic year",
    "Examination registration reminder",
    "Hostel quiet hours reminder",
}
REMOVED_EVENTS = {
    "AI Workshop on Campus Assistants",
    "Research Methodology Seminar",
    "Robotics Lab Tour",
    "Institute Technical Fest",
}
DEMO_SENTENCE = " DEMO DATA: this record was written for CampusCopilot and is not a DAVV record."

ROOT = Path(__file__).resolve().parents[2]

USERS = [
    ("Asha Menon", "admin@example.com", "Admin@12345", "admin", "DEMO account — not a DAVV record"),
    ("Rahul Iyer", "faculty@example.com", "Faculty@12345", "faculty", "DEMO account — not a DAVV record"),
    ("Meera Nair", "student@example.com", "Student@12345", "student", "DEMO account — not a DAVV record"),
    ("Arjun Das", "student2@example.com", "Student@12345", "student", "DEMO account — not a DAVV record"),
]

SAMPLE_COMPLAINTS = [
    ("Projector in LH-3 is dead", "The projector in lecture hall LH-3 does not switch on before class.", "Lecture hall LH-3", 40, "submitted", None),
    ("Hostel geyser cold", "The geyser in hostel block H2 room 214 is not heating water.", "Hostel H2", 28, "assigned", "faculty"),
    ("Morning bus missed the stop", "Campus bus route 4 did not arrive at the main stop this morning.", "Main gate", 18, "in_progress", "faculty"),
    ("Portal login failure", "I cannot log in to the student portal and the password reset mail never arrives.", None, 11, "resolved", "faculty"),
    ("Sticky laboratory desks", "Desks in the chemistry lab are sticky and were not wiped after the practical.", "Chemistry lab", 6, "submitted", None),
]


def upsert_users(db) -> dict[str, User]:
    found = {}
    for name, email, password, role, department in USERS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                full_name=name,
                email=email,
                password_hash=hash_password(password),
                role=role,
                department=department,
                is_active=True,
            )
            db.add(user)
            db.flush()
            print(f"Created {role} account {email}")
        user.is_demo = True
        user.department = department
        found[role if role != "student" else email] = user
    db.commit()
    return found


def remove_fictional_documents(db) -> None:
    rows = db.query(Document).all()
    for document in rows:
        fictional = document.original_filename in FICTIONAL_FILES or (
            document.description and "Fictional sample" in document.description
        )
        if not fictional:
            continue
        print(f"Removing invented document: {document.title}")
        delete_document(db, document)


def seed_documents(db, admin: User) -> None:
    remove_fictional_documents(db)
    manifest_path = ROOT / "data" / "official_documents" / "davv" / "manifest.json"
    folder = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest:
        if db.query(Document).filter(Document.source_url == item["source_url"]).first():
            print(f"Already stored: {item['title']}")
            continue
        path = folder / item["file"]
        retrieved = datetime.fromisoformat(item["retrieved_at"]).replace(tzinfo=timezone.utc)
        document = store_pdf(
            db,
            owner_id=admin.id,
            title=item["title"],
            category=item["category"],
            description="Public file retrieved from the DAVV website. The project did not rewrite it.",
            original_filename=item["file"],
            payload=path.read_bytes(),
            source_url=item["source_url"],
            source_page_url=item["source_page_url"],
            publication_date=item["publication_date"],
            retrieved_at=retrieved,
            provenance=item["provenance"],
        )
        print(f"Stored {document.title}: {document.status}, chunks={document.chunk_count}")


def seed_events(db, admin: User, student_two: User) -> None:
    for title in REMOVED_EVENTS:
        old = db.query(Event).filter(Event.title == title).first()
        if old is not None:
            print(f"Removing invented event: {title}")
            db.delete(old)
    db.commit()
    payload = json.loads((ROOT / "data" / "sample_events" / "events.json").read_text(encoding="utf-8"))
    now = utcnow()
    for item in payload:
        event = db.query(Event).filter(Event.title == item["title"]).first()
        if event is None:
            start = now + timedelta(days=item["days_from_now"])
            event = Event(
                title=item["title"],
                description=item["description"],
                venue=item["venue"],
                starts_at=start,
                ends_at=start + timedelta(hours=item["duration_hours"]),
                capacity=item["capacity"],
                is_demo=True,
                created_by=admin.id,
            )
            db.add(event)
            db.flush()
            print(f"Created event {event.title}")
        else:
            event.description = item["description"]
            event.venue = item["venue"]
            event.is_demo = True
        if item["title"] == "DEMO: one-seat tour":
            already = (
                db.query(EventRegistration)
                .filter(EventRegistration.event_id == event.id, EventRegistration.user_id == student_two.id)
                .first()
            )
            if already is None:
                db.add(EventRegistration(event_id=event.id, user_id=student_two.id, status="registered"))
                print("Filled the single DEMO: one-seat tour with the second sample student.")
    db.commit()


def seed_notices(db, admin: User) -> None:
    for title in REMOVED_NOTICES:
        old = db.query(Notice).filter(Notice.title == title).first()
        if old is not None:
            print(f"Removing invented notice: {title}")
            db.delete(old)
    db.commit()
    payload = json.loads((ROOT / "data" / "sample_notices" / "notices.json").read_text(encoding="utf-8"))
    for item in payload:
        if db.query(Notice).filter(Notice.title == item["title"]).first():
            continue
        result = summarise_notice(item["body"])
        deadlines, actions = dumps_result(result)
        db.add(
            Notice(
                title=item["title"],
                body=item["body"],
                audience=item["audience"],
                summary=result["summary"],
                summary_method=result["summary_method"],
                detected_audience=result["detected_audience"],
                deadlines_json=deadlines,
                action_items_json=actions,
                extraction_disclaimer=result["extraction_disclaimer"],
                source_url=item.get("source_url"),
                provenance=item.get("provenance", "demo"),
                created_by=admin.id,
            )
        )
        print(f"Created notice {item['title']} using {result['summary_method']}")
    db.commit()


def seed_complaints(db, student: User, faculty: User) -> None:
    for complaint in db.query(Complaint).all():
        complaint.is_demo = True
        if "DEMO DATA:" not in complaint.description:
            complaint.description = (complaint.description + DEMO_SENTENCE)[:4000]
    db.commit()
    if db.query(Complaint).count() > 0:
        print("Existing complaints were labelled DEMO DATA. No extra rows were added.")
        return
    for title, description, location, days_ago, status, assignee_key in SAMPLE_COMPLAINTS:
        complaint = create_complaint(
            db,
            user=student,
            title=title,
            description=description,
            location=location,
            user_category=None,
        )
        complaint.created_at = utcnow() - timedelta(days=days_ago)
        complaint.updated_at = complaint.created_at
        if assignee_key == "faculty":
            complaint.assigned_to = faculty.id
            complaint.department = faculty.department
        complaint.status = status
        complaint.is_demo = True
        if DEMO_SENTENCE.strip() not in complaint.description:
            complaint.description = (complaint.description + DEMO_SENTENCE)[:4000]
        if status == "resolved":
            complaint.resolution_remarks = "DEMO DATA resolution. This is not a DAVV decision."
        db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                actor_id=faculty.id if assignee_key else student.id,
                action="seed_status",
                to_status=status,
                note="Sample history row created by the seed script.",
            )
        )
        db.commit()
        print(f"Complaint #{complaint.id} {complaint.predicted_category} / {complaint.suggested_priority}")


def retrieval_check(db) -> None:
    result = answer_question(db, "How does Ordinance 9 say fellowships are awarded?")
    print("Ordinance 9 question mode:", result["answer_mode"])
    if result["sources"]:
        top = result["sources"][0]
        print(f"Top source: {top['document_title']} page {top['page_number']} score {top['score']}")
    else:
        print("WARNING: Ordinance 9 did not retrieve a chunk. Check the similarity threshold.")
    missing = answer_question(db, "What is the canteen menu on Wednesday?")
    print("Canteen question mode:", missing["answer_mode"], "sources:", len(missing["sources"]))


def main() -> None:
    init_db()
    db = get_session_factory()()
    try:
        users = upsert_users(db)
        admin = db.query(User).filter(User.email == "admin@example.com").one()
        faculty = db.query(User).filter(User.email == "faculty@example.com").one()
        student = db.query(User).filter(User.email == "student@example.com").one()
        student_two = db.query(User).filter(User.email == "student2@example.com").one()
        seed_documents(db, admin)
        seed_events(db, admin, student_two)
        seed_notices(db, admin)
        seed_complaints(db, student, faculty)
        retrieval_check(db)
        print("Sample accounts:")
        for _name, email, password, role, _department in USERS:
            print(f"  {role:8} {email}  {password}")
        print("These passwords are for the local demonstration only.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
