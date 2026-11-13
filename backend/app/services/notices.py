"""Extract a short summary, dates, and action lines from a notice.

Gemini is used only when the API key is configured and the call succeeds.
Otherwise the extractive fallback is used and labelled. Extracted dates are
never treated as verified facts.
"""

import json
import re

from app.constants import EXTRACTION_DISCLAIMER
from app.core.config import get_settings
from app.services.rag.generator import generate_with_gemini

DATE_RE = re.compile(
    r"\b(\d{1,2} [A-Z][a-z]+ \d{4}|[A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}:\d{2})\b"
)
ACTION_RE = re.compile(r"\b(must|should|submit|required|bring|carry|register|complete|deadline)\b", re.I)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return [part.strip() for part in parts if part.strip()]


def detect_audience(text: str) -> str:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("all students and faculty", "entire campus", "all members")):
        return "all"
    if "hostel" in lowered and "student" not in lowered:
        return "hostel"
    if "faculty" in lowered and "student" not in lowered:
        return "faculty"
    if "student" in lowered:
        return "students"
    return "all"


def extractive_notice(text: str) -> dict:
    sentences = _sentences(text)
    summary = " ".join(sentences[:3]) if sentences else text.strip()
    deadlines = []
    action_items = []
    for sentence in sentences:
        found_dates = DATE_RE.findall(sentence)
        if found_dates or "deadline" in sentence.lower():
            deadlines.append(
                {
                    "date_text": found_dates[0] if found_dates else None,
                    "description": sentence,
                    "verified": False,
                }
            )
        if ACTION_RE.search(sentence):
            action_items.append(sentence)
    # Keep the list short and stable for the interface.
    unique_actions = []
    for item in action_items:
        if item not in unique_actions:
            unique_actions.append(item)
    return {
        "summary": summary,
        "summary_method": "extractive_fallback",
        "detected_audience": detect_audience(text),
        "deadlines": deadlines[:8],
        "action_items": unique_actions[:8],
        "extraction_disclaimer": EXTRACTION_DISCLAIMER,
    }


def _gemini_notice(text: str) -> dict:
    prompt = (
        "Read the campus notice and return JSON only. Do not add facts that are not in the notice.\n"
        "Keys: summary (string), deadlines (list of objects with date_text and description), "
        "audience (one of all, students, faculty, hostel), action_items (list of strings).\n\n"
        f"Notice:\n{text}"
    )
    raw = generate_with_gemini(prompt)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("Gemini did not return JSON.")
    parsed = json.loads(raw[start : end + 1])
    deadlines = []
    for item in parsed.get("deadlines") or []:
        if isinstance(item, dict):
            deadlines.append(
                {
                    "date_text": item.get("date_text"),
                    "description": item.get("description") or "",
                    "verified": False,
                }
            )
    audience = parsed.get("audience") or detect_audience(text)
    if audience not in {"all", "students", "faculty", "hostel"}:
        audience = detect_audience(text)
    return {
        "summary": str(parsed.get("summary") or "").strip(),
        "summary_method": "gemini",
        "detected_audience": audience,
        "deadlines": deadlines[:8],
        "action_items": [str(item) for item in (parsed.get("action_items") or [])][:8],
        "extraction_disclaimer": EXTRACTION_DISCLAIMER,
    }


def summarise_notice(text: str) -> dict:
    mode = get_settings().resolved_llm_mode()
    if mode == "gemini":
        try:
            result = _gemini_notice(text)
            if result["summary"]:
                return result
        except Exception:
            fallback = extractive_notice(text)
            fallback["summary_method"] = "extractive_fallback_after_llm_error"
            return fallback
    return extractive_notice(text)


def dumps_result(result: dict) -> tuple[str, str]:
    return json.dumps(result["deadlines"]), json.dumps(result["action_items"])
