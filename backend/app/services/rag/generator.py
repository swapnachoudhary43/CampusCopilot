"""Build a grounded prompt and call Gemini when it is configured.

This module never invents an answer if the model call fails. The caller
decides whether to quote retrieved passages instead.
"""

from app.core.config import get_settings


def build_prompt(question: str, sources: list[dict], history: list[dict] | None = None) -> str:
    blocks = []
    for index, source in enumerate(sources, start=1):
        blocks.append(
            f"[{index}] Document: {source['document_title']} | Page: {source['page_number']}\n"
            f"{source['excerpt']}"
        )
    context = "\n---\n".join(blocks)
    history_lines = []
    for item in (history or [])[-4:]:
        history_lines.append(f"{item['role']}: {item['content'][:400]}")
    history_text = "\n".join(history_lines) if history_lines else "None"
    return (
        "You are CampusCopilot, a campus assistant for a student project demonstration.\n"
        "Answer the question using ONLY the institutional context below.\n"
        "If the context does not contain the answer, say that the uploaded documents "
        "do not contain enough information. Do not invent rules, dates, fees, or policies.\n"
        "When you use a fact, mention the document title and page number.\n"
        "Earlier chat messages are only for understanding follow-up questions. "
        "They are not a source of university rules.\n"
        "Write in clear, simple English.\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Institutional context:\n{context}\n\n"
        f"Student question: {question}\n"
    )


def quote_retrieved_passages(sources: list[dict], reason: str) -> str:
    lines = [
        reason,
        "",
    ]
    for index, source in enumerate(sources, start=1):
        lines.append(
            f"[{index}] {source['document_title']}, page {source['page_number']} "
            f"(similarity {source['score']:.2f})"
        )
        lines.append(f"\"{source['excerpt']}\"")
        lines.append("")
    lines.append("These passages were copied from the indexed documents. They were not rewritten by a language model.")
    return "\n".join(lines).strip()


def generate_with_gemini(prompt: str) -> str:
    settings = get_settings()
    if not settings.gemini_configured:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("The google-genai package is not installed.") from exc
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
    except Exception as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc
    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise RuntimeError("Gemini returned an empty response.")
    return str(text).strip()
