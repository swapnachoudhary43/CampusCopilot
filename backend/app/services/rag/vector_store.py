"""FAISS index of normalised document chunks.

Inner product on L2-normalised vectors is cosine similarity. The index is a
flat scan, which is the right choice for a few hundred campus chunks and is
easy to explain. The companion JSON file records chunk ids in index order.
"""

import json
import os

import numpy as np

from app.core.config import get_settings


def _load_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("faiss-cpu is not installed. Install backend/requirements.txt.") from exc
    return faiss


def rebuild_index(chunk_ids: list[int], vectors: np.ndarray, backend_name: str) -> int:
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    faiss = _load_faiss()
    if len(chunk_ids) == 0:
        if settings.faiss_index_path.exists():
            settings.faiss_index_path.unlink()
        if settings.faiss_meta_path.exists():
            settings.faiss_meta_path.unlink()
        return 0
    matrix = np.ascontiguousarray(vectors, dtype=np.float32)
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    temporary = settings.faiss_index_path.with_suffix(".index.tmp")
    faiss.write_index(index, str(temporary))
    os.replace(temporary, settings.faiss_index_path)
    meta = {
        "backend": backend_name,
        "embedding_model": settings.embedding_model,
        "dim": int(matrix.shape[1]),
        "chunk_ids": chunk_ids,
    }
    settings.faiss_meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return int(index.ntotal)


def search_index(query_vector: np.ndarray, top_k: int) -> list[tuple[int, float]]:
    settings = get_settings()
    if not settings.faiss_index_path.exists() or not settings.faiss_meta_path.exists():
        return []
    meta = json.loads(settings.faiss_meta_path.read_text(encoding="utf-8"))
    faiss = _load_faiss()
    index = faiss.read_index(str(settings.faiss_index_path))
    if index.ntotal == 0:
        return []
    query = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)
    saved_model = meta.get("embedding_model")
    if saved_model and saved_model != settings.embedding_model:
        raise RuntimeError(
            "The search index was built with a different embedding model. "
            "Use Rebuild search index before asking questions."
        )
    if query.shape[1] != meta["dim"]:
        raise RuntimeError(
            "The saved FAISS index does not match the current embedding size. "
            "Use Rebuild search index in Document management, or run the seed script again."
        )
    faiss.normalize_L2(query)
    k = min(top_k, index.ntotal)
    scores, positions = index.search(query, k)
    hits: list[tuple[int, float]] = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue
        hits.append((int(meta["chunk_ids"][int(position)]), float(score)))
    return hits


def index_backend_name() -> str | None:
    settings = get_settings()
    if not settings.faiss_meta_path.exists():
        return None
    meta = json.loads(settings.faiss_meta_path.read_text(encoding="utf-8"))
    return meta.get("backend")


def indexed_count() -> int:
    settings = get_settings()
    if not settings.faiss_meta_path.exists():
        return 0
    meta = json.loads(settings.faiss_meta_path.read_text(encoding="utf-8"))
    return len(meta.get("chunk_ids", []))
