"""Quiz-aware ranking: answers reorder close matches and ties are deterministic."""

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendRequest
from app.services.ranking import select_top_candidates


def _candidate(shoe_id: int, *, similarity: float | None = 0.5, tag_overlap: int | None = None, **fields) -> Candidate:
    fields.setdefault("price", 100.0)
    return Candidate(
        shoe_id=shoe_id,
        brand=fields.pop("brand", "Nike"),
        name=f"Shoe {shoe_id}",
        similarity=similarity,
        tag_overlap=tag_overlap,
        **fields,
    )


def _rated(**ratings) -> dict:
    return {"thehoopsgeek": ratings}


def _ids(picked: list[Candidate]) -> list[int]:
    return [c.shoe_id for c in picked]


def test_higher_similarity_wins_without_answers() -> None:
    candidates = [_candidate(1, similarity=0.4), _candidate(2, similarity=0.9), _candidate(3, similarity=0.6)]
    assert _ids(select_top_candidates(candidates, n=2)) == [2, 3]


def test_ties_break_by_review_score_then_id_regardless_of_request() -> None:
    candidates = [
        _candidate(1, metrics=_rated(overall=7.0)),
        _candidate(2, metrics=_rated(overall=9.0)),
        _candidate(3),
        _candidate(4),
    ]
    first = select_top_candidates(candidates, n=4)
    second = select_top_candidates(candidates, n=4, request=RecommendRequest(playstyle="all-black shoes"))
    assert _ids(first) == _ids(second) == [2, 1, 3, 4]


def test_fallback_ranks_by_tag_overlap() -> None:
    candidates = [_candidate(1, similarity=None, tag_overlap=0), _candidate(2, similarity=None, tag_overlap=2)]
    assert _ids(select_top_candidates(candidates, n=1)) == [2]


def test_priority_reorders_close_matches_and_gives_a_reason() -> None:
    candidates = [
        _candidate(1, similarity=0.52, metrics=_rated(traction=6.0)),
        _candidate(2, similarity=0.50, metrics=_rated(traction=9.5)),
    ]
    picked = select_top_candidates(candidates, n=2, request=RecommendRequest(priorities=["traction"]))
    assert _ids(picked) == [2, 1]
    assert picked[0].match_reasons == ["9.5 traction"]
    assert picked[1].match_reasons == []


def test_a_brand_preference_breaks_close_calls_but_is_not_a_filter() -> None:
    # Gaps are realistic: similarity spans under ~0.1 across a real candidate pool.
    request = RecommendRequest(preferred_brand="adidas")
    clearly_better = [_candidate(1, similarity=0.60), _candidate(2, similarity=0.54, brand="Adidas")]
    close_call = [_candidate(1, similarity=0.56), _candidate(2, similarity=0.54, brand="Adidas")]
    assert _ids(select_top_candidates(clearly_better, n=1, request=request)) == [1]
    assert _ids(select_top_candidates(close_call, n=1, request=request)) == [2]


def test_outdoor_court_prefers_durable_shoes_over_unknown_and_quotes_only_measured_data() -> None:
    candidates = [
        _candidate(1, metrics=_rated(outdoor="20%")),
        _candidate(2, metrics=_rated(outdoor="90%")),
        _candidate(3, specs={"outdoor_suitability": "good"}),
    ]
    picked = select_top_candidates(candidates, n=3, request=RecommendRequest(court="outdoor"))
    assert _ids(picked) == [3, 2, 1]
    assert picked[0].match_reasons == []  # unattributed spec: ranks, but isn't quoted
    assert picked[1].match_reasons == ["90% outdoor durability"]


def test_foot_width_brand_and_cut_add_reasons() -> None:
    candidate = _candidate(1, brand="Adidas", specs={"width_fit": "wide", "cut_height": "high"})
    request = RecommendRequest(foot_width="wide", preferred_brand="Adidas", preferred_cut="high")
    assert select_top_candidates([candidate], n=1, request=request)[0].match_reasons == ["Wide fit", "Adidas", "High cut"]


def test_lightweight_uses_shoe_weight() -> None:
    candidates = [_candidate(1, specs={"weight_oz": 15.5}), _candidate(2, specs={"weight_oz": 12.4})]
    picked = select_top_candidates(candidates, n=2, request=RecommendRequest(priorities=["lightweight"]))
    assert _ids(picked) == [2, 1]
    assert picked[0].match_reasons == ["12.4 oz"]


def test_position_tags_reward_matches_and_penalize_mismatches_but_ignore_untagged() -> None:
    candidates = [
        _candidate(1, specs={"position_tags": ["guard"]}),
        _candidate(2),
        _candidate(3, specs={"position_tags": ["big"]}),
    ]
    picked = select_top_candidates(candidates, n=3, request=RecommendRequest(playstyle="Big, Post"))
    assert _ids(picked) == [3, 2, 1]


def test_playstyle_tag_breaks_ties_and_unstated_styles_do_nothing() -> None:
    candidates = [_candidate(1), _candidate(2, specs={"playstyle_tags": ["shooter"]})]
    shooter = RecommendRequest(playstyle="Guard, Shooter")
    slasher = RecommendRequest(playstyle="Guard, Slasher")
    assert _ids(select_top_candidates(candidates, n=2, request=shooter)) == [2, 1]
    assert _ids(select_top_candidates(candidates, n=2, request=slasher)) == [1, 2]


def test_unpriced_shoes_lose_ties_to_priced_ones() -> None:
    candidates = [_candidate(1, price=None), _candidate(2)]
    assert _ids(select_top_candidates(candidates, n=1)) == [2]


def test_more_than_two_priorities_is_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RecommendRequest(priorities=["traction", "cushion", "support"])
