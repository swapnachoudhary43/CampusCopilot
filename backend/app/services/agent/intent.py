"""Choose a campus tool from the student's sentence.

This is a readable rule list, not a hidden model. A question about policy
is sent to document search even if it contains the word complaint.
"""

import re

QUESTION_START = re.compile(
    r"^(what|when|where|who|why|how|which|is|are|can|does|do|could|should)\b",
    re.IGNORECASE,
)
REGISTER_RE = re.compile(
    r"\b(register me|register for|sign me up|enrol me|enroll me|book me)\b",
    re.IGNORECASE,
)
STATUS_RE = re.compile(
    r"\b(my complaints|complaint status|status of (my )?complaint|track my complaint)\b",
    re.IGNORECASE,
)
SUBMIT_RE = re.compile(
    r"\b(i want to complain|file a complaint|submit a complaint|register a complaint|report a problem|report an issue)\b",
    re.IGNORECASE,
)
LIST_RE = re.compile(
    r"\b(upcoming events|list events|show me the events|show me events|what events|which events)\b",
    re.IGNORECASE,
)
CONFIRM_RE = re.compile(
    r"^(yes|y|confirm|ok|okay|proceed|submit|yes submit|yes, submit)[.!]?$",
    re.IGNORECASE,
)
CANCEL_RE = re.compile(r"^(no|n|cancel|stop|no thanks|no, cancel)[.!]?$", re.IGNORECASE)


def is_confirmation(text: str) -> bool:
    return bool(CONFIRM_RE.match(text.strip()))


def is_cancellation(text: str) -> bool:
    return bool(CANCEL_RE.match(text.strip()))


def detect_intent(text: str) -> str:
    if REGISTER_RE.search(text):
        return "register_for_event"
    if STATUS_RE.search(text):
        return "check_complaint_status"
    if SUBMIT_RE.search(text):
        return "submit_complaint"
    if LIST_RE.search(text) or (re.search(r"\bevents\b", text, re.IGNORECASE) and not QUESTION_START.match(text.strip())):
        return "list_available_events"
    return "search_campus_documents"


def extract_event_name(text: str) -> str | None:
    match = re.search(
        r"(?:register me for|register for|sign me up for|enroll me in|enrol me in|book me for)\s+(?:the\s+)?(.+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    name = re.split(r"\b(?:and then|and show|and list)\b", match.group(1), flags=re.IGNORECASE)[0]
    name = name.strip(" .?!")
    return name or None


def extract_complaint_id(text: str) -> int | None:
    match = re.search(r"\bcomplaint\s+#?(\d+)\b", text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def extract_complaint_fields(text: str) -> dict:
    cleaned = re.sub(
        r"^(please\s+)?(i want to|i would like to|i'd like to)\s+"
        r"(file\s+a\s+|submit\s+a\s+|register\s+a\s+)?complain(?:t)?\s*(about|that|regarding)?\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()
    if len(cleaned) < 10:
        cleaned = ""
    location = None
    if cleaned:
        located = re.search(
            r"\b(?:in|at|near)\s+(?:the\s+|my\s+)?([A-Za-z0-9][A-Za-z0-9 \-]{2,40})",
            cleaned,
        )
        if located:
            candidate = located.group(1).strip(" .")
            if len(candidate.split()) <= 6:
                location = candidate
    title = (cleaned or "Campus complaint")[:80].rstrip(" .")
    if len(title) < 5:
        title = "Campus complaint"
    return {
        "title": title[:120],
        "description": cleaned,
        "location": location,
    }
