"""Isolated API tests.

EMBEDDING_BACKEND=hash keeps the suite independent of the neural model download.
The running demonstration should keep sentence-transformers in backend/.env.
"""

import os
from datetime import timedelta

import pytest

os.environ.setdefault("EMBEDDING_BACKEND", "hash")
os.environ.setdefault("LLM_PROVIDER", "retrieval_only")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-campuscopilot-suite")
os.environ.setdefault("BCRYPT_ROUNDS", "4")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("LLM_PROVIDER", "retrieval_only")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-campuscopilot-suite")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.28")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.database.session import init_db, reset_database_state
    from app.services.ml.predict import clear_model_cache
    from app.services.rag.embeddings import SentenceTransformerEmbedder

    SentenceTransformerEmbedder._model = None
    reset_database_state()
    clear_model_cache()
    init_db()
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    reset_database_state()
    get_settings.cache_clear()
    clear_model_cache()


def register(client, email="meera@example.com", role_path="/api/auth/register", **extra):
    payload = {
        "full_name": extra.pop("full_name", "Meera Nair"),
        "email": email,
        "password": extra.pop("password", "Student@12345"),
        "department": "AI and Data Science",
    }
    response = client.post(role_path, json=payload)
    return response


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def pdf_bytes(text: str) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(72, 72, 540, 800), text, fontsize=12)
    payload = document.tobytes()
    document.close()
    return payload
