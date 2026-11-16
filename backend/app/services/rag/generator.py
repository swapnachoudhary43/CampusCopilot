"""Build a grounded prompt and call Gemini when it is configured.

The model id comes from GEMINI_MODEL. A failed call never becomes a made-up
answer. The caller quotes the retrieved passages instead.
"""

import logging
import time

from app.core.config import get_settings

logger = logging.getLogger("campuscopilot.gemini")

_TRANSIENT = {429, 500, 502, 503, 504}
_PERMANENT = {400, 401, 403, 404}


class GeminiError(Exception):
    """A user-safe Gemini failure. The technical cause is logged, not returned."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def build_prompt(question: str, sources: list[dict], history: list[dict] | None = None) -> str:
    blocks = []
    for index, source in enumerate(sources, start=1):
        source = source or {}
        title = str(source.get("document_title") or "Untitled document")
        page_number = source.get("page_number")
        date = source.get("publication_date") or "not recorded"
        url = source.get("source_url") or "not recorded"
        excerpt = str(source.get("excerpt") or "").strip()
        page_text = f" | Page: {page_number}" if page_number is not None else ""
        blocks.append(
            f"[{index}] Document: {title}{page_text} | Publication date: {date} | Source URL: {url}\n{excerpt}"
        )
    context = "\n---\n".join(blocks) if blocks else "None"
    history_lines = []
    for item in (history or [])[-4:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "unknown")
        content = item.get("content") or ""
        history_lines.append(f"{role}: {str(content)[:400]}")
    history_text = "\n".join(history_lines) if history_lines else "None"
    return (
        "You are CampusCopilot. Answer ONLY from the retrieved institutional evidence below.\n"
        "Write every answer in clear English, regardless of the question, conversation history, or source language.\n"
        "Do not use Hindi, Hinglish, Devanagari, or Hindi transliterated into Latin letters. Translate relevant source content into English; retain course codes and numbers.\n"
        "Answer the exact question directly and keep the response concise. Include only facts needed to answer it.\n"
        "Do not list related facts just because they share a keyword with the question.\n"
        "If the question names a department, programme, semester, or date range, include only matching evidence.\n"
        "If a question names a specific faculty or school, give only the rule applicable to it; do not list exceptions for other faculties.\n"
        "When a university-wide rule has a general category for faculties other than named exceptions, apply that category to a named school when the evidence shows it is not one of the exceptions. State that the school-specific rule is not separately listed instead of refusing only because the school's name is absent.\n"
        "Treat different criteria explicitly assigned to different faculties as separate rules, not as a conflict.\n"
        "For a latest-notice question, give the newest verifiable notice for each named department. Use a notice's own date when shown; do not treat page footers, crawl/index timestamps, event dates, or academic-session dates as publication dates. A page-level 'Issued on' date dates that page or edition, not each listed notice.\n"
        "If a department's latest listed notice has no publication date, name the item and say its publication date is not shown. If only old notices are listed, state that plainly without treating a footer or navigation link as a newer notice.\n"
        "For a timetable question, give only the requested programme and semester rows.\n"
        "Use short inline source citations such as [1]. Put ordinance clause numbers in parentheses, not inside source-citation brackets.\n"
        "Do not reproduce whole passages, add generic disclaimers, or describe retrieval steps.\n"
        "Source titles and links are shown separately; do not add a separate source list to the answer.\n"
        "Do not invent policies, dates, fees, percentages, or placement rates.\n"
        "Do not infer a requirement that is not written in the evidence.\n"
        "If the evidence is insufficient, say so.\n"
        "If two passages disagree, say that they conflict and quote both. Do not merge them into one rule.\n"
        "If one ordinance states different attendance percentages for different faculties, report each figure with its faculty.\n"
        "Earlier chat messages explain follow-up questions. They are not a source of rules.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Retrieved evidence:\n{context}\n\n"
        f"Student question: {question}\n"
    )


def quote_retrieved_passages(
    sources: list[dict],
    reason: str,
    excerpt_limit: int | None = None,
) -> str:
    lines = [reason] if reason else []
    for index, source in enumerate(sources[:2], start=1):
        excerpt = str((source or {}).get("excerpt") or "").strip()
        if excerpt:
            if excerpt_limit is not None:
                excerpt = excerpt[:excerpt_limit].rstrip()
            lines.append(f"[{index}] {excerpt}")
    return "\n\n".join(lines)


def _extract_response_text(response: object) -> str | None:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        for candidate in candidates:
            parts = getattr(candidate, "content", None)
            if parts is None:
                parts = candidate.get("content") if isinstance(candidate, dict) else None
            if isinstance(parts, dict):
                parts = parts.get("parts") or []
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, dict):
                    text = part.get("text")
                else:
                    text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


def _status_code(exc: Exception) -> int | None:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    error = getattr(exc, "error", None)
    if isinstance(error, dict):
        for attr in ("status", "code"):
            value = error.get(attr)
            if isinstance(value, int):
                return value
    text = str(exc)
    for code in (400, 401, 403, 404, 429, 500, 502, 503, 504):
        if str(code) in text:
            return code
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered or "connection" in lowered:
        return 504
    return None


def _user_message(code: int | None) -> str:
    if code in (401, 403):
        return "The AI generation service rejected the API key. The verified campus evidence is shown below."
    if code in (400, 404):
        return (
            "The AI generation service is not configured with a supported model. "
            "The verified campus evidence is shown below."
        )
    return "The AI generation service is temporarily unavailable. The verified campus evidence is shown below."


def generate_with_gemini(prompt: str) -> str:
    settings = get_settings()
    if not settings.gemini_configured:
        raise GeminiError("GEMINI_API_KEY is not set.")
    try:
        from google import genai
    except ImportError as exc:
        logger.error("google-genai is not installed: %s", exc)
        raise GeminiError("The AI generation service is not installed. The verified campus evidence is shown below.") from exc
    client = genai.Client(api_key=settings.gemini_api_key)
    last_code = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
            text = _extract_response_text(response)
            if not text:
                raise GeminiError("The AI generation service returned an empty answer. The verified campus evidence is shown below.")
            return text
        except GeminiError:
            raise
        except Exception as exc:
            last_code = _status_code(exc)
            logger.warning("Gemini attempt %s failed with status %s: %s", attempt + 1, last_code, exc)
            if last_code in _PERMANENT:
                raise GeminiError(_user_message(last_code)) from exc
            if last_code in _TRANSIENT and attempt < 2:
                time.sleep(0.4 * (2 ** attempt))
                continue
            if last_code is None and attempt < 2:
                time.sleep(0.4 * (2 ** attempt))
                continue
            raise GeminiError(_user_message(last_code)) from exc
    raise GeminiError(_user_message(last_code))
