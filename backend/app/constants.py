"""Shared labels used by the database, APIs, and the sample dataset.

Keeping these in one file stops the classifier labels, the complaint form,
and the priority rules from drifting apart.
"""

ROLES = ("student", "faculty", "admin")

COMPLAINT_CATEGORIES = (
    "Infrastructure",
    "Hostel",
    "Transportation",
    "IT Support",
    "Library",
    "Academic",
    "Cleanliness",
    "Other",
)

COMPLAINT_STATUSES = (
    "submitted",
    "assigned",
    "in_progress",
    "resolved",
    "closed",
)

# Faculty may move a complaint only along this path.
# Administrators use the same path so status history stays meaningful.
STATUS_TRANSITIONS = {
    "submitted": {"assigned", "in_progress"},
    "assigned": {"in_progress", "resolved"},
    "in_progress": {"resolved"},
    "resolved": {"closed"},
    "closed": set(),
}

DOCUMENT_CATEGORIES = (
    "Regulations",
    "Examinations",
    "Attendance",
    "Fees",
    "Hostel",
    "Scholarship",
    "Calendar",
    "Syllabus",
    "Circular",
    "Other",
)

NOTICE_AUDIENCES = ("all", "students", "faculty", "hostel")

PRIORITY_LEVELS = ("low", "medium", "high")

PRIORITY_DISCLAIMER = (
    "This priority is a transparent keyword rule, not a trained machine-learning model. "
    "An administrator should confirm it."
)

EXTRACTION_DISCLAIMER = (
    "Dates, action items, and the detected audience were extracted automatically. "
    "They are not verified facts."
)
