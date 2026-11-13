"""Shoe traits from review prose, each backed by a quote. Today: "bouncy" cushioning.

    python -m pipeline.tags.review_traits              # extract for changed shoes
    python -m pipeline.tags.review_traits --dry-run    # count what would be sent, no API calls

Runs beside ``pipeline.tags.review_tags``, between ``pipeline.run`` and
``pipeline.upsert.writer``. Results live in ``staging/review_traits.json``,
keyed by canonical id with a fingerprint of the sentences sent, so re-runs
only pay for shoes whose reviews changed. The writer stores them as
``specs.trait_tags`` plus the quotes in ``extra_metadata.review_traits``.

Only sentences that talk about bounce are sent. A trait is kept only when the
model's quote appears verbatim in them, describes the trait, and isn't negated
or hedged ("no bounce", "slightly bouncy"): nearly every Zoom shoe gets called
a little bouncy, so only standout bounce earns it.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pipeline.tags.review_tags import STAGING_DIR, JsonLLM, _fold, fingerprint

logger = logging.getLogger(__name__)

CANONICAL = STAGING_DIR / "canonical.json"
REVIEW_TRAITS = STAGING_DIR / "review_traits.json"

TRAITS = ("bouncy",)
TRAIT_WORDS = {
    "bouncy": re.compile(r"\b(?:bounc\w*|spring\w*|energy return|propuls\w*|trampoline)", re.I),
}
_NEGATED = re.compile(
    r"\b(?:no|not|lacks?|lacking|without|little|zero|minimal|isn['’]t|doesn['’]t|never|too firm)\b"
    r"[^.!?]{0,30}\b(?:bounc|spring|energy return|propuls)",
    re.I,
)
# Reviewers call most Zoom setups "slightly bouncy"; only standout bounce counts.
_HEDGED = re.compile(
    r"\b(?:slight(?:ly)?|a (?:bit|touch|little)|some|mild(?:ly)?|modest(?:ly)?|somewhat|hint of|bit of|decent)\b"
    r"[^.!?]{0,20}\b(?:bounc|spring|energy return|propuls)",
    re.I,
)
MAX_SENTENCES = 12
MAX_SENTENCE_CHARS = 400
WORKERS = 6

SYSTEM_PROMPT = """You tag basketball shoes using ONLY the review sentences given.
Tag "bouncy" only when bounce is a standout trait: a sentence says the cushioning is very bouncy or springy, gives high/great energy return, or feels like a trampoline.
Do not tag it for mild or hedged bounce ("slightly bouncy", "some bounce", "a bit springy"), when a sentence says the shoe lacks bounce or is low and flat, or when the bounce is about something else (e.g. the ball, a player).
Copy a short exact quote from a sentence that supports the tag. If nothing qualifies, return an empty list."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "traits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tag": {"type": "string", "enum": list(TRAITS)}, "quote": {"type": "string"}},
                "required": ["tag", "quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["traits"],
    "additionalProperties": False,
}


def sentences(shoe: dict[str, Any]) -> list[str]:
    """Review sentences that mention bounce, in source order."""
    found: list[str] = []
    for field in ("review_text", "pros", "cons"):
        for item in shoe.get(field) or []:
            for sentence in re.split(r"(?<=[.!?])\s+", item.get("text") or ""):
                sentence = re.sub(r"^\[[^\]]+\]\s*", "", sentence.strip())
                if sentence and any(p.search(sentence) for p in TRAIT_WORDS.values()) and sentence not in found:
                    found.append(sentence[:MAX_SENTENCE_CHARS])
    return found[:MAX_SENTENCES]


def verified_traits(raw: dict[str, Any], texts: list[str]) -> list[dict[str, str]]:
    corpus = _fold(" ".join(texts))
    kept: list[dict[str, str]] = []
    for item in raw.get("traits") or []:
        tag, quote = item.get("tag"), (item.get("quote") or "").strip()
        if tag not in TRAITS or any(k["tag"] == tag for k in kept) or not quote:
            continue
        if _fold(quote) in corpus and TRAIT_WORDS[tag].search(quote) and not _NEGATED.search(quote) and not _HEDGED.search(quote):
            kept.append({"tag": tag, "quote": quote})
    return kept


def extract_one(shoe: dict[str, Any], llm: JsonLLM) -> dict[str, Any]:
    texts = sentences(shoe)
    entry: dict[str, Any] = {"fingerprint": fingerprint(texts), "traits": []}
    if not texts:
        return entry
    numbered = "\n".join(f"[{i}] {text}" for i, text in enumerate(texts, 1))
    raw = llm.complete_json(
        system=SYSTEM_PROMPT,
        user=f"Shoe: {shoe['brand']} {shoe['model']}\n\nSentences:\n{numbered}",
        schema_name="ShoeTraits",
        schema=SCHEMA,
    )
    return {**entry, "traits": verified_traits(raw, texts)}


def stale_shoes(canonical: list[dict[str, Any]], cache: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        shoe
        for shoe in canonical
        if (cache.get(shoe["canonical_id"]) or {}).get("fingerprint") != fingerprint(sentences(shoe))
    ]


def update_cache(
    canonical: list[dict[str, Any]], cache: dict[str, Any], llm: JsonLLM
) -> tuple[dict[str, Any], int, int]:
    """Re-extract stale shoes and drop entries for shoes no longer scraped."""
    todo = stale_shoes(canonical, cache)
    updated = {s["canonical_id"]: cache[s["canonical_id"]] for s in canonical if s["canonical_id"] in cache}
    failed = 0

    def run(shoe: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        try:
            return shoe["canonical_id"], extract_one(shoe, llm)
        except Exception as exc:  # one bad response shouldn't sink the batch
            logger.warning("trait extraction failed for %s: %s", shoe["canonical_id"], exc)
            return shoe["canonical_id"], None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for canonical_id, entry in pool.map(run, todo):
            if entry is None:
                failed += 1
            else:
                updated[canonical_id] = entry
    return updated, len(todo), failed


def apply_review_traits(shoe: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Shoe dict with ``trait_tags`` and the quotes behind them."""
    entry = cache.get(shoe["canonical_id"])
    if not entry or not entry["traits"]:
        return shoe
    return {
        **shoe,
        "trait_tags": [item["tag"] for item in entry["traits"]],
        "review_traits": entry["traits"],
    }


def load_cache(path: Path = REVIEW_TRAITS) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.tags.review_traits", description=__doc__)
    parser.add_argument("--staging", type=Path, default=CANONICAL)
    parser.add_argument("--out", type=Path, default=REVIEW_TRAITS)
    parser.add_argument("--dry-run", action="store_true", help="count stale shoes; no API calls")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    canonical = json.loads(args.staging.read_text(encoding="utf-8"))
    cache = load_cache(args.out) or {}
    if args.dry_run:
        stale = stale_shoes(canonical, cache)
        with_text = sum(1 for shoe in stale if sentences(shoe))
        logger.info("dry run: %d of %d shoes need extraction (%d with bounce sentences)", len(stale), len(canonical), with_text)
        return 0

    from shared.llm import get_llm_client

    updated, attempted, failed = update_cache(canonical, cache, get_llm_client())
    args.out.write_text(json.dumps(updated, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {tag: sum(1 for e in updated.values() if any(t["tag"] == tag for t in e["traits"])) for tag in TRAITS}
    logger.info("extracted=%d failed=%d cached=%d traits=%s -> %s", attempted - failed, failed, len(updated), counts, args.out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
