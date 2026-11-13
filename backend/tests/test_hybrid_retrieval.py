"""Keyword retrieval regression tests for clauses missed by cosine threshold."""

from types import SimpleNamespace

from app.services.rag.pipeline import _lexical_rank


def test_bm25_finds_attendance_percentage_clause():
    ordinance = SimpleNamespace(title="Ordinance No. 6 — Examinations (General)")
    target = SimpleNamespace(
        id=101,
        document=ordinance,
        text=(
            "The minimum attendance requirement for prosecution of a regular course "
            "of study shall be seventy five percent of lectures and practicals."
        ),
    )
    distractor = SimpleNamespace(
        id=102,
        document=ordinance,
        text=(
            "Where a candidate seeks an additional subject, the minimum attendance "
            "requirement shall apply equally in that additional subject."
        ),
    )
    unrelated = SimpleNamespace(
        id=103,
        document=SimpleNamespace(title="Academic Calendar"),
        text="The semester shall have a minimum of ninety days of actual teaching.",
    )

    ranked = _lexical_rank(
        [distractor, unrelated, target],
        "What attendance percentage is required under Ordinance No. 6 for a regular course of study?",
    )

    assert ranked
    assert ranked[0][0] == 101
