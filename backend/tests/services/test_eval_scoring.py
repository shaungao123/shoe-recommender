"""The eval's grading rules, using made-up shoes and no database."""

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendRequest
from eval.cases import CASES, Case
from eval.run_eval import answer_fit, grade, label, regressions

CASE = Case("sample", {"playstyle": "Guard"}, good=(r"Kyrie",), bad=(r"LeBron",))


def _shoe(name: str, brand: str = "Nike", **fields) -> Candidate:
    fields.setdefault("price", 100.0)
    return Candidate(shoe_id=1, brand=brand, name=name, **fields)


def test_labels_are_good_bad_or_unlabeled_and_bad_wins() -> None:
    assert label(_shoe("Kyrie 4"), CASE) == 1
    assert label(_shoe("LeBron 20"), CASE) == -1
    assert label(_shoe("Precision 7"), CASE) == 0
    overlap = Case("overlap", {"playstyle": "Guard"}, good=(r"Kobe",), bad=(r"Kobe 4",))
    assert label(_shoe("Kobe 4 Protro"), overlap) == -1


def test_grade_counts_budget_violations_and_brand_capture() -> None:
    request = RecommendRequest(playstyle="Guard", budget=100, preferred_brand="Nike")
    row = grade([_shoe("Kyrie 4", price=120.0), _shoe("LeBron 20", price=90.0)], CASE, request)
    assert row["label_score"] == 0
    assert row["over_budget"] == 1
    assert row["all_preferred_brand"] is True


def test_answer_fit_is_none_without_stated_preferences() -> None:
    assert answer_fit(_shoe("Kyrie 4"), RecommendRequest(playstyle="Guard", court="indoor")) is None


def test_answer_fit_scores_each_preference() -> None:
    request = RecommendRequest(priorities=["traction"], preferred_cut="high")
    shoe = _shoe(
        "Kyrie 4",
        metrics={"thehoopsgeek": {"traction": 9.0}},
        specs={"cut_height": "low"},
    )
    assert answer_fit(shoe, request) == 0.5


def test_regressions_only_flag_real_drops() -> None:
    results = {
        "a": {"boosted": {"label_score": 0.2}},
        "b": {"boosted": {"label_score": 0.5}},
        "new": {"boosted": {"label_score": -1.0}},
    }
    assert regressions(results, {"a": 0.6, "b": 0.5}) == ["a: +0.60 -> +0.20"]


def test_every_case_is_a_valid_request_with_a_unique_id() -> None:
    for case in CASES:
        RecommendRequest(**case.request)
    assert len({case.id for case in CASES}) == len(CASES)
