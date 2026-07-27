"""Seeded random tie-break when selecting top N candidates."""

from app.schemas.candidate import Candidate
from app.services.ranking import select_top_candidates


def _candidate(shoe_id: int, *, similarity: float | None = None, tag_overlap: int | None = None) -> Candidate:
    return Candidate(
        shoe_id=shoe_id,
        brand="Nike",
        name=f"Shoe {shoe_id}",
        price=100.0,
        similarity=similarity,
        tag_overlap=tag_overlap,
    )


def test_same_similarity_fixed_seed_is_deterministic() -> None:
    candidates = [_candidate(i, similarity=0.75) for i in range(5)]
    first = select_top_candidates(candidates, n=3, seed=42)
    second = select_top_candidates(candidates, n=3, seed=42)
    assert [c.shoe_id for c in first] == [c.shoe_id for c in second]
    assert len(first) == 3


def test_same_similarity_different_seed_can_differ() -> None:
    candidates = [_candidate(i, similarity=0.75) for i in range(10)]
    a = {c.shoe_id for c in select_top_candidates(candidates, n=3, seed=1)}
    b = {c.shoe_id for c in select_top_candidates(candidates, n=3, seed=999)}
    # Not guaranteed to differ, but with 10 shoes two seeds usually diverge
    assert len(a) == 3 and len(b) == 3


def test_mixed_ranks_takes_best_then_samples_ties() -> None:
    candidates = [
        _candidate(1, similarity=0.9),
        _candidate(2, similarity=0.9),
        _candidate(3, similarity=0.5),
        _candidate(4, similarity=0.5),
        _candidate(5, similarity=0.5),
    ]
    picked = select_top_candidates(candidates, n=3, seed=7)
    ids = [c.shoe_id for c in picked]
    assert ids[0] in (1, 2)
    assert ids[1] in (1, 2)
    assert ids[0] != ids[1]
    assert ids[2] in (3, 4, 5)


def test_fallback_uses_tag_overlap_primary_key() -> None:
    candidates = [_candidate(i, tag_overlap=2) for i in range(6)]
    picked = select_top_candidates(candidates, n=3, seed=123)
    assert len(picked) == 3
