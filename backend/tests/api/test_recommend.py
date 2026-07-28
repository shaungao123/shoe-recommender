"""API tests for POST /api/recommend — mocks only, no OpenAI."""

from decimal import Decimal

import pytest

from app.schemas.candidate import Candidate, ReviewSnippet
from shared.embedding import EmbeddingError
from shared.llm import LLMError
from tests.conftest import seed_shoe


@pytest.fixture(autouse=True)
def _force_template_explainer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip live chat API; public explain() falls back to the template path."""

    def boom(*args, **kwargs):
        raise LLMError("tests use template explainer")

    monkeypatch.setattr("app.services.rag.explainer_llm.explain", boom)


def test_recommend_empty_corpus_returns_empty_list(client, monkeypatch: pytest.MonkeyPatch):
    def boom(*args, **kwargs):
        raise EmbeddingError("no credits")

    monkeypatch.setattr("app.services.recommend.retrieve", boom)

    res = client.post(
        "/api/recommend",
        json={"playstyle": "slasher guard", "budget": 150, "aesthetic": None},
    )
    assert res.status_code == 200
    assert res.json() == {"recommendations": []}


def test_recommend_frontend_shape_uses_fallback(client, db_session, monkeypatch: pytest.MonkeyPatch):
    seed_shoe(db_session)
    seed_shoe(
        db_session,
        canonical_id="nike-lebron-22",
        name="LeBron 22",
        price=Decimal("160.00"),
        specs={
            "playstyle_tags": ["post"],
            "position_tags": ["big"],
            "cut_height": "mid",
            "outdoor_suitability": "fair",
            "width_fit": "standard",
            "cushioning_tech": "Zoom Air",
        },
    )

    def boom(*args, **kwargs):
        raise EmbeddingError("quota")

    monkeypatch.setattr("app.services.recommend.retrieve", boom)

    res = client.post(
        "/api/recommend",
        json={
            "playstyle": "slasher guard",
            "budget": 200,
            "aesthetic": "low profile black",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "recommendations" in body
    assert 1 <= len(body["recommendations"]) <= 3
    top = body["recommendations"][0]
    assert top["brand"] == "Nike"
    assert top["model"] == "G.T. Cut 3"
    assert top["price"] == 190.0
    assert isinstance(top["specs"], list)
    assert isinstance(top["explanation"], str) and top["explanation"]
    assert top["similarity"] is None  # fallback marker


def test_recommend_passes_hard_filters(client, db_session, monkeypatch: pytest.MonkeyPatch):
    seed_shoe(db_session)  # fair outdoor
    seed_shoe(
        db_session,
        canonical_id="outdoor-slasher",
        name="Outdoor Slasher",
        price=Decimal("140.00"),
        specs={
            "playstyle_tags": ["slasher"],
            "position_tags": ["guard"],
            "outdoor_suitability": "good",
            "cut_height": "low",
            "width_fit": "standard",
        },
    )

    def boom(*args, **kwargs):
        raise EmbeddingError("quota")

    monkeypatch.setattr("app.services.recommend.retrieve", boom)

    res = client.post(
        "/api/recommend",
        json={
            "playstyle": "slasher",
            "budget": 200,
            "outdoor": "good",
            "cut": "low",
        },
    )
    assert res.status_code == 200
    models = [r["model"] for r in res.json()["recommendations"]]
    assert models == ["Outdoor Slasher"]


def test_recommend_vector_path_mocked(client, db_session, monkeypatch: pytest.MonkeyPatch):
    row = seed_shoe(db_session)

    def fake_retrieve(*args, **kwargs):
        return [
            Candidate(
                shoe_id=row.id,
                brand=row.brand,
                name=row.name,
                price=float(row.price),
                image_url=row.image_url,
                affiliate_url=row.affiliate_url,
                specs=row.specs or {},
                snippets=[
                    ReviewSnippet(text="Elite court feel.", source="runrepeat")
                ],
                similarity=0.88,
            ),
            Candidate(
                shoe_id=row.id + 1,
                brand="Jordan",
                name="Extra",
                price=120.0,
                specs={},
                similarity=0.5,
            ),
            Candidate(
                shoe_id=row.id + 2,
                brand="Adidas",
                name="Third",
                price=110.0,
                specs={},
                similarity=0.4,
            ),
            Candidate(
                shoe_id=row.id + 3,
                brand="Puma",
                name="Fourth",
                price=100.0,
                specs={},
                similarity=0.3,
            ),
        ]

    monkeypatch.setattr("app.services.recommend.retrieve", fake_retrieve)

    res = client.post(
        "/api/recommend",
        json={"playstyle": "guard", "budget": 200, "aesthetic": "clean"},
    )
    assert res.status_code == 200
    recs = res.json()["recommendations"]
    assert len(recs) == 3
    assert recs[0]["model"] == "G.T. Cut 3"
    assert recs[0]["similarity"] == pytest.approx(0.88)
    assert "runrepeat" in recs[0]["explanation"]
    assert "Elite court feel" in recs[0]["explanation"]


def test_recommend_empty_vector_hits_falls_back(client, db_session, monkeypatch: pytest.MonkeyPatch):
    seed_shoe(db_session)

    monkeypatch.setattr("app.services.recommend.retrieve", lambda *a, **k: [])

    res = client.post(
        "/api/recommend",
        json={"playstyle": "slasher", "budget": 250},
    )
    assert res.status_code == 200
    assert len(res.json()["recommendations"]) == 1
    assert res.json()["recommendations"][0]["model"] == "G.T. Cut 3"


def test_recommend_validation_requires_at_least_one_criterion(client, db_session):
    res = client.post("/api/recommend", json={})
    assert res.status_code == 422

    res = client.post("/api/recommend", json={"playstyle": "   "})
    assert res.status_code == 422

    seed_shoe(db_session)
    res = client.post("/api/recommend", json={"budget": 150})
    assert res.status_code == 200

    res = client.post("/api/recommend", json={"outdoor": "good"})
    assert res.status_code == 200
