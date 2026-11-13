"""Lexical search over stored chunks.

BM25 keeps exact words such as ordinance numbers, course codes, and
"students placed" that a semantic index can rank below a nearby page.
"""

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "the", "of", "for", "to", "in", "on", "at", "and", "or", "is", "are",
    "was", "be", "by", "with", "from", "that", "this", "what", "how", "does", "do",
    "give", "me", "please", "about",
}


def tokens(text: str) -> list[str]:
    return [item for item in _TOKEN.findall(text.lower()) if item not in _STOP and len(item) > 1]


def bm25_ranks(documents: list[tuple[int, str]], query: str, top_k: int = 20) -> list[tuple[int, float]]:
    """Return (document id, BM25 score) for the strongest lexical matches."""
    query_terms = tokens(query)
    if not query_terms or not documents:
        return []
    parsed = [(doc_id, tokens(text)) for doc_id, text in documents]
    doc_count = len(parsed)
    avg = sum(len(words) for _doc_id, words in parsed) / doc_count
    df: Counter[str] = Counter()
    for _doc_id, words in parsed:
        df.update(set(words))
    k1 = 1.5
    b = 0.75
    scored: list[tuple[int, float]] = []
    for doc_id, words in parsed:
        if not words:
            continue
        counts = Counter(words)
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if frequency == 0:
                continue
            idf = math.log(1 + (doc_count - df[term] + 0.5) / (df[term] + 0.5))
            denom = frequency + k1 * (1 - b + b * len(words) / avg)
            score += idf * (frequency * (k1 + 1)) / denom
        lowered = " ".join(words)
        query_lower = " ".join(query_terms)
        if any(word in query_lower for word in ("rate", "placement", "ctc", "placed")) and (
            "lpa" in lowered or "placed" in lowered or "offers" in lowered
        ):
            score += 2.5
        if score > 0:
            scored.append((doc_id, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def reciprocal_rank_fusion(rankings: list[list[int]], constant: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (constant + position)
    return fused
