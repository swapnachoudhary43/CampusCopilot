"""Chunking does not depend on the database or the embedding model."""

from app.services.rag.chunking import chunk_pages


def test_long_page_is_split_with_overlap():
    chunks = chunk_pages([(2, "word " * 400)], size=200, overlap=40)
    assert len(chunks) > 1
    assert all(chunk.page_number == 2 for chunk in chunks)
    assert chunks[0].chunk_index == 0
