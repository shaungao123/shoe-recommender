"""Review-tag extraction with a fake LLM — no network."""

from pipeline.tags.review_tags import (
    apply_review_tags,
    fingerprint,
    passages,
    stale_shoes,
    update_cache,
    verified_tags,
)

REVIEW = "Best for bigger players who need a very supportive shoe. Great for guards too."


def _shoe(cid: str = "nb-kawhi-1", text: str = REVIEW, **fields) -> dict:
    return {
        "canonical_id": cid,
        "brand": "New Balance",
        "model": "Kawhi 1",
        "review_text": [{"source": "weartesters", "text": text}],
        **fields,
    }


class FakeLLM:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = 0

    def complete_json(self, **_: object) -> dict:
        self.calls += 1
        return self.response


def test_quotes_must_be_verbatim_and_name_the_player() -> None:
    raw = {
        "positions": [
            {"tag": "big", "quote": "Best for bigger players who need a very supportive shoe."},
            {"tag": "wing", "quote": "Great for wings"},  # not in the text
            {"tag": "guard", "quote": "a very supportive shoe"},  # doesn't name guards
        ],
        "playstyles": [{"tag": "all-around", "quote": "Great for guards too."}],  # not allowed
    }
    kept = verified_tags(raw, [REVIEW])
    assert [i["tag"] for i in kept["positions"]] == ["big"]
    assert kept["playstyles"] == []


def test_only_relevant_passages_are_sent() -> None:
    shoe = _shoe(pros=[{"source": "x", "text": "Nice colorways"}])
    assert passages(shoe) == [REVIEW]


def test_cache_skips_unchanged_shoes_and_redoes_changed_ones() -> None:
    llm = FakeLLM({"positions": [{"tag": "big", "quote": "bigger players"}], "playstyles": []})
    cache, attempted, failed = update_cache([_shoe()], {}, llm)
    assert (attempted, failed, llm.calls) == (1, 0, 1)
    assert stale_shoes([_shoe()], cache) == []
    changed = _shoe(text=REVIEW + " Perfect for post players.")
    assert stale_shoes([changed], cache) == [changed]


def test_dropped_shoes_leave_the_cache_and_failures_are_counted() -> None:
    class Broken:
        def complete_json(self, **_: object) -> dict:
            raise RuntimeError("bad response")

    cache = {"gone": {"fingerprint": "x", "positions": [], "playstyles": []}}
    updated, attempted, failed = update_cache([_shoe()], cache, Broken())
    assert updated == {}
    assert (attempted, failed) == (1, 1)


def test_apply_adds_tags_and_quotes_without_removing_scraped_ones() -> None:
    entry = {
        "fingerprint": fingerprint([REVIEW]),
        "positions": [{"tag": "big", "quote": "bigger players"}, {"tag": "guard", "quote": "guards"}],
        "playstyles": [],
    }
    shoe = _shoe(position_tags=["guard"], playstyle_tags=["shooter"])
    merged = apply_review_tags(shoe, {"nb-kawhi-1": entry})
    assert merged["position_tags"] == ["guard", "big"]
    assert merged["playstyle_tags"] == ["shooter"]
    assert merged["review_tags"]["positions"][0]["quote"] == "bigger players"
    assert apply_review_tags(shoe, {}) is shoe
