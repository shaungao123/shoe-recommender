"""Retriever tests — query text, fallback ranking, candidate mapping.

The pgvector query itself (cosine_distance) needs real Postgres and is
exercised by the eval harness / integration runs, not unit tests.
"""

from decimal import Decimal

import pytest

from app.db.repositories.shoes import ChunkHit, ShoeMatch
from app.services.rag import retriever
from shared.db.models import Shoe
from shared.embedding import EmbeddingError


def make_shoe(name: str, price: str, playstyle_tags: list[str] | None = None, **overrides) -> Shoe:
    values = {
        "canonical_id": f"nike-{name.lower().replace(' ', '-')}",
        "brand": "Nike",
        "name": name,
        "price": Decimal(price),
        "currency": "USD",
        "specs": {"playstyle_tags": playstyle_tags or [], "position_tags": []},
        "extra_metadata": {},
    }
    values.update(overrides)
    return Shoe(**values)


def test_build_query_text_includes_both_inputs() -> None:
    text = retriever.build_query_text("explosive slasher guard", "clean white minimal")
    assert "explosive slasher guard" in text
    assert "clean white minimal" in text


def test_build_query_text_skips_empty_aesthetic() -> None:
    text = retriever.build_query_text("shooter", "  ")
    assert "Style" not in text
    assert "shooter" in text


def test_build_query_text_aesthetic_only() -> None:
    text = retriever.build_query_text("", "clean white minimal")
    assert "clean white minimal" in text
    assert "player" not in text


def test_fallback_filters_budget_and_ranks_by_tag_overlap(db_session) -> None:
    db_session.add_all(
        [
            make_shoe("Pricey", "220", ["slasher"]),
            make_shoe("Match", "150", ["slasher", "speedster"]),
            make_shoe("NoMatch", "170", ["post"]),
        ]
    )
    db_session.flush()

    candidates = retriever.retrieve_fallback(
        db_session, playstyle="fast slasher speedster guard", budget=200
    )

    names = [c.name for c in candidates]
    assert "Pricey" not in names  # over budget
    assert names[0] == "Match"  # 2 tag hits beats 0
    assert all(c.similarity is None for c in candidates)  # no-vector marker


def test_fallback_null_budget_includes_all_prices(db_session) -> None:
    db_session.add_all(
        [
            make_shoe("Pricey", "220", ["slasher"]),
            make_shoe("Cheap", "90", ["slasher"]),
        ]
    )
    db_session.flush()

    names = [
        c.name
        for c in retriever.retrieve_fallback(
            db_session, playstyle="slasher", budget=None
        )
    ]
    assert "Pricey" in names
    assert "Cheap" in names


def test_fallback_respects_hard_filters(db_session) -> None:
    db_session.add_all(
        [
            make_shoe(
                "Outdoor",
                "150",
                ["slasher"],
                specs={
                    "playstyle_tags": ["slasher"],
                    "position_tags": ["guard"],
                    "outdoor_suitability": "good",
                    "cut_height": "low",
                },
            ),
            make_shoe(
                "Indoor",
                "140",
                ["slasher"],
                specs={
                    "playstyle_tags": ["slasher"],
                    "position_tags": ["guard"],
                    "outdoor_suitability": "bad",
                    "cut_height": "low",
                },
            ),
        ]
    )
    db_session.flush()

    candidates = retriever.retrieve_fallback(
        db_session,
        playstyle="slasher",
        budget=200,
        outdoor="good",
        cut="low",
    )
    assert [c.name for c in candidates] == ["Outdoor"]


def test_fallback_tag_matching_uses_word_boundaries_and_synonyms(db_session) -> None:
    db_session.add_all(
        [
            make_shoe("Boundary", "150", ["post"]),  # must not match "poster"
            make_shoe("Synonym", "140", ["speedster"]),  # "shifty" is a synonym
        ]
    )
    db_session.flush()

    candidates = retriever.retrieve_fallback(
        db_session, playstyle="shifty guard who hangs posters", budget=200
    )

    assert candidates[0].name == "Synonym"


def test_fallback_respects_limit(db_session) -> None:
    db_session.add_all(make_shoe(f"Shoe {i}", "100") for i in range(15))
    db_session.flush()
    assert len(retriever.retrieve_fallback(db_session, "guard", budget=500)) == retriever.DEFAULT_LIMIT


def test_retrieve_wires_budget_model_and_maps_candidates(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    shoe = make_shoe("LeBron 21", "160", ["post"])
    db_session.add(shoe)
    db_session.flush()

    class FakeClient:
        model_id = "test-model"

        def embed_one(self, text: str) -> list[float]:
            self.query_text = text
            return [0.1, 0.2]

    captured: dict = {}

    def fake_search(session, query_vector, model_id, limit, snippets_per_shoe, **filters):
        captured.update(
            vector=query_vector,
            model_id=model_id,
            budget_max=filters.get("budget_max"),
            brand=filters.get("brand"),
            outdoor=filters.get("outdoor"),
            limit=limit,
        )
        return [
            ShoeMatch(
                shoe=shoe,
                distance=0.25,
                chunks=[ChunkHit(content="Great traction.", source="weartesters", distance=0.25)],
            )
        ]

    monkeypatch.setattr(retriever, "search_candidates", fake_search)
    client = FakeClient()

    candidates = retriever.retrieve(
        db_session,
        playstyle="post scorer",
        budget=180,
        aesthetic="retro",
        client=client,
        brand="Nike",
        outdoor="fair",
    )

    assert captured["budget_max"] == 180
    assert captured["brand"] == "Nike"
    assert captured["outdoor"] == "fair"
    assert captured["model_id"] == "test-model"
    assert captured["vector"] == [0.1, 0.2]

    (candidate,) = candidates
    assert candidate.shoe_id == shoe.id
    assert candidate.brand == "Nike"
    assert candidate.price == 160.0
    assert candidate.specs["playstyle_tags"] == ["post"]
    assert candidate.similarity == pytest.approx(0.75)
    assert candidate.snippets[0].text == "Great traction."
    assert candidate.snippets[0].source == "weartesters"


def test_retrieve_raises_embedding_error(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomClient:
        model_id = "test-model"

        def embed_one(self, text: str) -> list[float]:
            raise EmbeddingError("quota")

    with pytest.raises(EmbeddingError, match="quota"):
        retriever.retrieve(
            db_session,
            playstyle="guard",
            budget=150,
            aesthetic="",
            client=BoomClient(),
        )
