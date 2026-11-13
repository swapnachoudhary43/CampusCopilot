"""Graceful fallback when Gemini is unavailable."""

from types import SimpleNamespace

from app.services.rag import pipeline


def test_gemini_failure_falls_back_to_cited_passages(monkeypatch):
    source = {
        "document_id": 1,
        "document_title": "Attendance Policy",
        "page_number": 2,
        "excerpt": "The minimum attendance requirement is described in this passage.",
        "score": 0.71,
    }
    settings = SimpleNamespace(
        similarity_threshold=0.48,
        embedding_backend="sentence-transformers",
        resolved_llm_mode=lambda: "gemini",
    )
    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)
    monkeypatch.setattr(pipeline, "retrieve", lambda _db, _query: [source])
    monkeypatch.setattr(pipeline, "build_prompt", lambda *_args: "prompt")

    def unavailable(_prompt):
        raise RuntimeError("Gemini request failed: 503 UNAVAILABLE")

    monkeypatch.setattr(pipeline, "generate_with_gemini", unavailable)

    result = pipeline.answer_question(None, "What is the attendance requirement?")

    assert result["answer_mode"] == "gemini_fallback"
    assert "Gemini is temporarily unavailable" in result["answer"]
    assert "Attendance Policy, page 2" in result["answer"]
    assert "not a generated answer" in result["answer"]
    assert "503 UNAVAILABLE" in result["llm_error"]
