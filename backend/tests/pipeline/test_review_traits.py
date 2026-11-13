"""Bounce trait extraction with a fake LLM — no network."""

from pipeline.tags.review_traits import (
    apply_review_traits,
    sentences,
    stale_shoes,
    update_cache,
    verified_traits,
)

BOUNCY = "The forefoot has a springy, bouncy feel on takeoff."
FLAT = "It sits low to the ground with no bounce at all."


def _shoe(*texts: str, cid: str = "nike-gt-jump-2") -> dict:
    return {
        "canonical_id": cid,
        "brand": "Nike",
        "model": "G.T. Jump 2",
        "review_text": [{"source": "weartesters", "text": "[cushion] " + " ".join(texts)}],
    }


class FakeLLM:
    def __init__(self, response: dict) -> None:
        self.response, self.calls = response, 0

    def complete_json(self, **_: object) -> dict:
        self.calls += 1
        return self.response


def test_only_bounce_sentences_are_sent():
    assert sentences(_shoe("Traction is great.", BOUNCY, FLAT)) == [BOUNCY, FLAT]
    assert sentences(_shoe("Traction is great.")) == []


def test_quote_must_be_verbatim_about_bounce_and_not_negated():
    texts = [BOUNCY, FLAT]
    assert verified_traits({"traits": [{"tag": "bouncy", "quote": "springy, bouncy feel"}]}, texts) == [
        {"tag": "bouncy", "quote": "springy, bouncy feel"}
    ]
    texts.append("Responsive and slightly bouncy, with some spring.")
    for quote in ("no bounce at all", "super bouncy cushion", "low to the ground", "slightly bouncy", "some spring"):
        assert verified_traits({"traits": [{"tag": "bouncy", "quote": quote}]}, texts) == []
    assert verified_traits({"traits": [{"tag": "plush", "quote": "springy, bouncy feel"}]}, texts) == []


def test_shoes_without_bounce_sentences_skip_the_llm_and_cache_works():
    llm = FakeLLM({"traits": [{"tag": "bouncy", "quote": "springy, bouncy feel"}]})
    quiet = _shoe("Traction is great.", cid="quiet")
    cache, attempted, failed = update_cache([_shoe(BOUNCY), quiet], {}, llm)
    assert (attempted, failed, llm.calls) == (2, 0, 1)
    assert cache["quiet"]["traits"] == []
    assert stale_shoes([_shoe(BOUNCY), quiet], cache) == []


def test_apply_adds_trait_tags_and_quotes():
    cache = {"nike-gt-jump-2": {"fingerprint": "x", "traits": [{"tag": "bouncy", "quote": "springy"}]}}
    shoe = apply_review_traits(_shoe(BOUNCY), cache)
    assert shoe["trait_tags"] == ["bouncy"]
    assert shoe["review_traits"] == [{"tag": "bouncy", "quote": "springy"}]
    plain = _shoe(FLAT, cid="other")
    assert apply_review_traits(plain, cache) is plain
