"""Deterministic explainer — grounded in Candidate fields only."""

from app.schemas.candidate import Candidate, ReviewSnippet
from app.services.rag.explainer import explain


def test_explain_picks_top_three_and_builds_chips() -> None:
    candidates = [
        Candidate(
            shoe_id=i,
            brand="Nike",
            name=f"Shoe {i}",
            price=100.0 + i,
            specs={
                "playstyle_tags": ["slasher"],
                "position_tags": ["guard"],
                "cut_height": "low",
                "cushioning_tech": "ZoomX",
            },
            snippets=[
                ReviewSnippet(text="Sticky traction on dusty courts.", source="weartesters")
            ],
            similarity=0.9 - i * 0.1,
        )
        for i in range(5)
    ]

    recs = explain(candidates[:3], playstyle="slasher guard")
    assert len(recs) == 3
    assert recs[0].model == "Shoe 0"
    assert recs[0].id == 0
    assert "slasher" in recs[0].specs
    assert "guard" in recs[0].specs
    assert "weartesters" in recs[0].explanation
    assert "Sticky traction" in recs[0].explanation
    assert recs[0].similarity == 0.9


def test_explain_empty_candidates() -> None:
    assert explain([]) == []
