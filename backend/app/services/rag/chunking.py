"""Split extracted PDF text into overlapping chunks.

A chunk is a short passage stored with its page number. Overlap keeps a
sentence that crosses a boundary available in both neighbouring chunks.
"""

from dataclasses import dataclass


@dataclass
class TextChunk:
    page_number: int
    chunk_index: int
    text: str


def chunk_pages(pages: list[tuple[int, str]], size: int = 900, overlap: int = 150) -> list[TextChunk]:
    if size <= overlap:
        raise ValueError("Chunk size must be larger than the overlap.")
    chunks: list[TextChunk] = []
    for page_number, raw_text in pages:
        cleaned = " ".join((raw_text or "").split())
        if not cleaned:
            continue
        start = 0
        local_index = 0
        while start < len(cleaned):
            end = min(len(cleaned), start + size)
            if end < len(cleaned):
                space = cleaned.rfind(" ", start + size // 2, end)
                if space != -1:
                    end = space
            piece = cleaned[start:end].strip()
            if piece:
                chunks.append(TextChunk(page_number=page_number, chunk_index=local_index, text=piece))
                local_index += 1
            if end >= len(cleaned):
                break
            next_start = max(end - overlap, start + 1)
            start = next_start
    return chunks
