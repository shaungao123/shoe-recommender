"""Corpus embedder tests — chunk building is pure; sync runs on SQLite."""

from decimal import Decimal

from sqlalchemy import select

from pipeline.embed.embed_corpus import (
    MAX_CHUNK_CHARS,
    build_chunks,
    build_spec_summary,
    sync_embeddings,
)
from shared.db.models import Embedding, Shoe


class FakeEmbeddingClient:
    """Stands in for shared.embedding.EmbeddingClient in sync tests."""

    def __init__(self, model_id: str = "test-model") -> None:
        self.model_id = model_id
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.0, 0.0, 0.0] for _ in texts]


def make_shoe(**overrides) -> Shoe:
    values = {
        "canonical_id": "nike-lebron-21",
        "brand": "Nike",
        "name": "LeBron 21",
        "price": Decimal("160.00"),
        "currency": "USD",
        "specs": {
            "signature_player": "LeBron James",
            "cut_height": "mid",
            "cushioning_tech": "Zoom Air",
            "weight_oz": 15.2,
            "outdoor_suitability": "fair",
            "position_tags": ["big", "wing"],
            "playstyle_tags": ["post", "all-around"],
        },
        "extra_metadata": {
            "review_text": [
                {"source": "weartesters", "text": "Traction was sticky on clean floors."},
                {"source": "runrepeat", "text": "The heel stack measured 31.5 mm in our lab."},
            ],
            "pros": [
                {"source": "runrepeat", "text": "Great impact protection"},
                {"source": "weartesters", "text": "Supportive fit"},
            ],
            "cons": [{"source": "runrepeat", "text": "Heavy"}],
        },
    }
    values.update(overrides)
    return Shoe(**values)


def test_spec_summary_omits_price_when_null() -> None:
    summary = build_spec_summary(make_shoe(price=None))
    assert "price:" not in summary
    assert summary.endswith(".")


def test_spec_summary_reads_like_prose() -> None:
    summary = build_spec_summary(make_shoe())
    assert "Nike LeBron 21" in summary
    assert "signature shoe of LeBron James" in summary
    assert "mid cut" in summary
    assert "playstyles: post, all-around" in summary
    assert "price: $160" in summary


def test_build_chunks_groups_by_source() -> None:
    chunks = build_chunks(make_shoe())
    spec_chunks = [c for c in chunks if c.source is None]
    assert len(spec_chunks) == 1

    review_sources = {c.source for c in chunks if "Traction" in c.content or "heel stack" in c.content}
    assert review_sources == {"weartesters", "runrepeat"}

    # pros and cons from the same source land in one chunk, prefixed with the shoe
    rr_proscons = [c for c in chunks if "Pros:" in c.content and c.source == "runrepeat"]
    assert len(rr_proscons) == 1
    assert "Great impact protection" in rr_proscons[0].content
    assert "Cons: Heavy" in rr_proscons[0].content
    assert rr_proscons[0].content.startswith("Nike LeBron 21")


def test_build_chunks_splits_long_reviews() -> None:
    long_text = ". ".join(f"Sentence number {i} about the shoe" for i in range(200))
    shoe = make_shoe(
        extra_metadata={"review_text": [{"source": "weartesters", "text": long_text}]}
    )
    chunks = [c for c in build_chunks(shoe) if c.source == "weartesters"]
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHUNK_CHARS + 50 for c in chunks)  # + title prefix


def test_build_chunks_dedupes_repeated_text() -> None:
    shoe = make_shoe(
        extra_metadata={
            "review_text": [
                {"source": "weartesters", "text": "Same segment."},
                {"source": "weartesters", "text": "Same segment."},
            ]
        }
    )
    contents = [c.content for c in build_chunks(shoe)]
    assert len(contents) == len(set(contents))


def test_sync_embeds_new_corpus(db_session) -> None:
    db_session.add(make_shoe())
    db_session.flush()
    client = FakeEmbeddingClient()

    result = sync_embeddings(db_session, client)

    assert result.shoes == 1
    assert result.embedded > 0
    assert result.kept == 0
    rows = db_session.scalars(select(Embedding)).all()
    assert len(rows) == result.embedded
    assert all(row.model_id == "test-model" for row in rows)


def test_sync_is_idempotent_and_never_reembeds(db_session) -> None:
    db_session.add(make_shoe())
    db_session.flush()
    client = FakeEmbeddingClient()
    first = sync_embeddings(db_session, client)
    db_session.flush()

    client.calls.clear()
    second = sync_embeddings(db_session, client)

    assert second.kept == first.embedded
    assert second.embedded == 0
    assert second.deleted == 0
    assert client.calls == []


def test_sync_replaces_rows_from_old_model(db_session) -> None:
    db_session.add(make_shoe())
    db_session.flush()
    sync_embeddings(db_session, FakeEmbeddingClient(model_id="old-model"))
    db_session.flush()

    result = sync_embeddings(db_session, FakeEmbeddingClient(model_id="new-model"))
    db_session.flush()

    assert result.deleted > 0
    assert result.embedded == result.deleted
    models = {row.model_id for row in db_session.scalars(select(Embedding))}
    assert models == {"new-model"}


def test_sync_dry_run_makes_no_api_calls(db_session) -> None:
    db_session.add(make_shoe())
    db_session.flush()
    client = FakeEmbeddingClient()

    result = sync_embeddings(db_session, client, dry_run=True)

    assert result.embedded > 0
    assert client.calls == []
    assert db_session.scalars(select(Embedding)).all() == []


def test_sync_dry_run_stages_no_deletes(db_session) -> None:
    """A commit after a dry run must not delete rows the run only counted."""
    db_session.add(make_shoe())
    db_session.flush()
    sync_embeddings(db_session, FakeEmbeddingClient(model_id="old-model"))
    db_session.flush()
    before = len(db_session.scalars(select(Embedding)).all())

    result = sync_embeddings(
        db_session, FakeEmbeddingClient(model_id="new-model"), dry_run=True
    )
    db_session.commit()

    assert result.deleted == before  # counted...
    assert len(db_session.scalars(select(Embedding)).all()) == before  # ...not applied


def test_split_never_drops_text() -> None:
    # paragraph over the budget falls back to sentence splits within it
    long_paragraph = ". ".join(f"Sentence {i} about traction" for i in range(120))
    text = f"Short intro.\n\n{long_paragraph}"
    shoe = make_shoe(extra_metadata={"review_text": [{"source": "weartesters", "text": text}]})
    chunks = [c for c in build_chunks(shoe) if c.source == "weartesters"]
    joined = " ".join(c.content for c in chunks)
    assert "Sentence 119" in joined  # the tail survived

    # no boundaries at all: sliced into windows, nothing dropped
    # (non-repeating content so the chunk dedupe can't collapse windows)
    blob = "".join(f"{i:04d}" for i in range((MAX_CHUNK_CHARS * 2 + 100) // 4))
    shoe = make_shoe(extra_metadata={"review_text": [{"source": "runrepeat", "text": blob}]})
    chunks = [c for c in build_chunks(shoe) if c.source == "runrepeat"]
    assert sum(len(c.content) - len("Nike LeBron 21 — ") for c in chunks) == len(blob)


def test_build_chunks_keeps_same_text_from_two_sources() -> None:
    shoe = make_shoe(
        extra_metadata={
            "review_text": [
                {"source": "weartesters", "text": "Great traction."},
                {"source": "runrepeat", "text": "Great traction."},
            ]
        }
    )
    matching = [c for c in build_chunks(shoe) if "Great traction" in c.content]
    assert {c.source for c in matching} == {"weartesters", "runrepeat"}
