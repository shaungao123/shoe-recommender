"""Saved preferences and the personal verdict — fake embeddings, no network."""

from __future__ import annotations

import pytest

from app.api.routes.recommend import get_embed_client
from app.schemas.candidate import Candidate
from app.schemas.preferences import Preferences
from app.services.verdict import fit_notes, level_for_rank, profile_text
from shared.embedding import EmbeddingError
from tests.conftest import seed_shoe

ANSWERS = {
    "positions": ["guard"],
    "styles": ["slasher"],
    "description": "quick first step",
    "court": "indoor",
    "priorities": ["traction"],
    "budget": 140,
    "foot_width": "wide",
    "preferred_brand": "Nike",
    "preferred_cut": "low",
    "note": "recovering from an ankle sprain",
}


class FakeEmbedder:
    model_id = "fake-model"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def embed_one(self, text: str) -> list[float]:
        self.calls += 1
        if self.fail:
            raise EmbeddingError("down")
        return [0.1] * 1536


@pytest.fixture()
def embedder(auth_client):
    fake = FakeEmbedder()
    auth_client.app.dependency_overrides[get_embed_client] = lambda: fake
    yield fake
    auth_client.app.dependency_overrides.pop(get_embed_client, None)


def test_preferences_and_verdict_require_auth(client):
    assert client.get("/api/me/preferences").status_code == 401
    assert client.put("/api/me/preferences", json=ANSWERS).status_code == 401
    assert client.get("/api/me/verdict/1").status_code == 401


def test_save_and_read_preferences(auth_client, embedder):
    assert auth_client.get("/api/me/preferences").status_code == 404

    saved = auth_client.put("/api/me/preferences", json=ANSWERS)
    assert saved.status_code == 200
    body = auth_client.get("/api/me/preferences").json()
    assert {k: body[k] for k in ANSWERS} == ANSWERS
    assert "updated_at" in body
    assert embedder.calls == 1

    # Same answers: the stored profile vector is reused, not re-embedded.
    auth_client.put("/api/me/preferences", json=ANSWERS)
    assert embedder.calls == 1
    auth_client.put("/api/me/preferences", json={**ANSWERS, "note": ""})
    assert embedder.calls == 2
    assert auth_client.get("/api/me/preferences").json()["note"] == ""


def test_invalid_answers_are_rejected(auth_client, embedder):
    assert auth_client.put("/api/me/preferences", json={"positions": ["point"]}).status_code == 422
    assert auth_client.put("/api/me/preferences", json={"priorities": ["traction", "cushion", "support"]}).status_code == 422
    assert auth_client.put("/api/me/preferences", json={"mood": "happy"}).status_code == 422


def test_saving_still_works_when_embedding_fails(auth_client):
    auth_client.app.dependency_overrides[get_embed_client] = lambda: FakeEmbedder(fail=True)
    try:
        assert auth_client.put("/api/me/preferences", json=ANSWERS).status_code == 200
    finally:
        auth_client.app.dependency_overrides.pop(get_embed_client, None)


def test_verdict_without_preferences(auth_client, db_session, embedder):
    shoe = seed_shoe(db_session)
    body = auth_client.get(f"/api/me/verdict/{shoe.id}").json()
    assert body == {"has_preferences": False, "verdict": None}
    assert auth_client.get("/api/me/verdict/999999").status_code == 404


def _seed_catalog(db_session, count: int = 20):
    return [
        seed_shoe(db_session, canonical_id=f"shoe-{i}", name=f"Shoe {i}", price=None if i % 3 else 100)
        for i in range(count)
    ]


def test_verdict_comes_from_rank_in_the_whole_catalog(auth_client, db_session, embedder, monkeypatch):
    shoes = _seed_catalog(db_session)
    # Similarity falls with the index, so shoe 0 ranks first and shoe 19 last.
    similarity = {shoe.id: 0.9 - i * 0.01 for i, shoe in enumerate(shoes)}
    monkeypatch.setattr("app.services.verdict.best_similarity_by_shoe", lambda *a: similarity)
    auth_client.put("/api/me/preferences", json={"positions": ["guard"]})

    levels = [auth_client.get(f"/api/me/verdict/{shoe.id}").json()["verdict"]["level"] for shoe in shoes]
    # 20 shoes: top 5% = 1 shoe, top 30% = 6 shoes. Unpriced shoes aren't penalised.
    assert levels == ["great"] + ["worth_a_look"] * 5 + ["not_for_you"] * 14


def test_verdict_falls_back_to_tag_overlap_without_embeddings(auth_client, db_session, monkeypatch):
    shoes = _seed_catalog(db_session, count=4)
    auth_client.app.dependency_overrides[get_embed_client] = lambda: FakeEmbedder(fail=True)
    try:
        auth_client.put("/api/me/preferences", json=ANSWERS)
        body = auth_client.get(f"/api/me/verdict/{shoes[0].id}").json()
    finally:
        auth_client.app.dependency_overrides.pop(get_embed_client, None)
    assert body["has_preferences"] is True
    assert body["verdict"]["label"] == "Great fit for you"


@pytest.mark.parametrize(
    ("index", "level"),
    [(0, "great"), (32, "great"), (33, "worth_a_look"), (197, "worth_a_look"), (198, "not_for_you")],
)
def test_cutoffs_for_a_660_shoe_catalog(index, level):
    assert level_for_rank(index, 660) == level


def _candidate(**specs) -> Candidate:
    return Candidate(
        shoe_id=1,
        brand="Nike",
        name="Sabrina 2",
        price=130.0,
        specs=specs,
        metrics={"thehoopsgeek": {"traction": 9.1, "cushion": 6.4}},
    )


def test_fit_notes_lead_with_matches_and_flag_problems():
    prefs = Preferences(
        positions=["guard"], styles=["slasher"], priorities=["traction", "cushion"],
        foot_width="wide", preferred_cut="low", preferred_brand="Nike",
    )
    reasons, caveats, unknowns = fit_notes(
        _candidate(position_tags=["guard"], playstyle_tags=["slasher"], width_fit="narrow", cut_height="mid"),
        prefs,
    )
    assert reasons == ["9.1 traction — your top priority", "Built for guards", "Suits slashers"]
    assert caveats == ["Only 6.4 cushion, and you want strong cushion", "Runs narrow for wide feet"]
    assert unknowns == []


def test_fit_notes_say_what_is_unknown():
    prefs = Preferences(priorities=["support", "lightweight"], court="outdoor", foot_width="narrow")
    reasons, caveats, unknowns = fit_notes(_candidate(), prefs)
    assert reasons == [] and caveats == []
    assert unknowns == ["No support rating yet", "No weight listed"]


def test_fit_notes_position_mismatch_names_who_it_is_for():
    prefs = Preferences(positions=["guard"])
    _, caveats, _ = fit_notes(_candidate(position_tags=["wing", "big"]), prefs)
    assert caveats == ["Built more for wings and bigs"]


def test_profile_text_matches_the_recommender_query():
    prefs = Preferences(**ANSWERS)
    text = profile_text(prefs)
    assert text.startswith("Basketball shoe for a Guard — Slasher — quick first step — recovering from an ankle sprain")
    assert "Plays indoors." in text and "Cares most about traction." in text
    assert profile_text(Preferences()) == ""
