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
        date = source.get("publication_date") or "not recorded"
        url = source.get("source_url") or "not recorded"
        blocks.append(
            f"[{index}] Document: {source['document_title']} | Page: {source['page_number']} | "
            f"Publication date: {date} | Source URL: {url}\n{source['excerpt']}"
        )
    context = "\n---\n".join(blocks) if blocks else "None"
    history_lines = []
    for item in (history or [])[-4:]:
        history_lines.append(f"{item['role']}: {item['content'][:400]}")
    history_text = "\n".join(history_lines) if history_lines else "None"
    return (
        "You are CampusCopilot. Answer ONLY from the retrieved institutional evidence below.\n"
        "Do not invent policies, dates, fees, percentages, or placement rates.\n"
        "Do not infer a requirement that is not written in the evidence.\n"
        "If the evidence is insufficient, say so.\n"
        "If two passages disagree, say that they conflict and quote both. Do not merge them into one rule.\n"
        "If one ordinance states different attendance percentages for different faculties, report each figure with its faculty.\n"
        "When you use a fact, name the document title and page.\n"
        "Earlier chat messages explain follow-up questions. They are not a source of rules.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Retrieved evidence:\n{context}\n\n"
        f"Student question: {question}\n"
    )


def _score_label(source: dict) -> str:
    method = source.get("retrieval_method")
    if method == "title_only":
        return "matching file name, no searchable text"
    if method == "hybrid":
        return (
            f"semantic {float(source.get('semantic_score') or 0):.2f}, "
            f"keyword {float(source.get('lexical_score') or 0):.2f}"
        )
    return f"score {float(source.get('score') or 0):.2f}"


def quote_retrieved_passages(sources: list[dict], reason: str) -> str:
    lines = [reason, ""]
    for index, source in enumerate(sources, start=1):
        page = source.get("page_number")
        page_text = f", page {page}" if page else ""
        lines.append(f"[{index}] {source['document_title']}{page_text} ({_score_label(source)})")
        excerpt = source.get("excerpt") or ""
        if excerpt:
            lines.append(f"\"{excerpt}\"")
        lines.append("")
    lines.append("These passages were copied from the indexed documents. They were not rewritten by a language model.")
    return "\n".join(lines).strip()


def _status_code(exc: Exception) -> int | None:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
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
            text = getattr(response, "text", None)
            if not text or not str(text).strip():
                raise GeminiError("The AI generation service returned an empty answer. The verified campus evidence is shown below.")
            return str(text).strip()
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
