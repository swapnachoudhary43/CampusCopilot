"""Turn text into vectors.

The demonstration backend is Sentence Transformers. Tests use a hash
embedder so they do not download a neural model. The hash embedder is not
semantic search and must not be used for the viva demonstration.
"""

import hashlib
import re

import numpy as np

from app.core.config import get_settings

HASH_DIM = 384
# Used only by the test embedder. The neural model handles common words itself.
HASH_STOPWORDS = {
    "a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "at", "is", "are",
    "was", "be", "this", "that", "it", "my", "me", "what", "how", "when", "where",
    "who", "why", "do", "does", "did", "with", "from", "by", "about",
}


class HashEmbedder:
    """Bag-of-tokens vectors for tests. Shared words raise the cosine score."""

    name = "hash-v1"
    dim = HASH_DIM

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = [
                token
                for token in re.findall(r"[a-z0-9]+", text.lower())
                if token not in HASH_STOPWORDS
            ]
            if not tokens:
                vectors[row, 0] = 1.0
                continue
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                index = int(digest[:8], 16) % self.dim
                vectors[row, index] += 1.0
            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm
        return vectors


class SentenceTransformerEmbedder:
    """Semantic embeddings from a local Sentence Transformers model."""

    _model = None
    _loaded_name = None

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.name = model_name

    def embed(self, texts: list[str]) -> np.ndarray:
        if (
            SentenceTransformerEmbedder._model is None
            or SentenceTransformerEmbedder._loaded_name != self.model_name
        ):
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is not installed. Install backend/requirements.txt."
                ) from exc
            try:
                SentenceTransformerEmbedder._model = SentenceTransformer(self.model_name)
                SentenceTransformerEmbedder._loaded_name = self.model_name
            except Exception as exc:
                raise RuntimeError(
                    "The embedding model could not be loaded. Check the internet connection "
                    f"and EMBEDDING_MODEL ({self.model_name}). Original error: {exc}"
                ) from exc
        vectors = SentenceTransformerEmbedder._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


def get_embedder():
    settings = get_settings()
    if settings.embedding_backend.strip().lower() == "hash":
        return HashEmbedder()
    if settings.embedding_backend.strip().lower() != "sentence-transformers":
        raise RuntimeError(
            "EMBEDDING_BACKEND must be 'sentence-transformers' or 'hash'. "
            "Use sentence-transformers for the demonstration."
        )
    return SentenceTransformerEmbedder(settings.embedding_model)
