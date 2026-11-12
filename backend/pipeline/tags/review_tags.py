"""Position and playstyle tags extracted from review prose, each backed by a quote.

    python -m pipeline.tags.review_tags              # extract for changed shoes
    python -m pipeline.tags.review_tags --dry-run    # count what would be sent, no API calls

Runs between ``pipeline.run`` and ``pipeline.upsert.writer``. Reads
``staging/canonical.json`` and keeps results in ``staging/review_tags.json``,
keyed by canonical id with a fingerprint of the review text, so re-runs only
pay for shoes whose reviews changed. The writer merges these tags into the
scraped ones; without this file it refuses to run, so a re-import can't
silently drop them.

A tag is kept only when the model's quote appears verbatim in the reviews and
names that kind of player — generic praise like "solid all-around performer"
never earns a position.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

STAGING_DIR = Path(__file__).resolve().parent.parent / "staging"
CANONICAL = STAGING_DIR / "canonical.json"
REVIEW_TAGS = STAGING_DIR / "review_tags.json"

KINDS = {"positions": "position_tags", "playstyles": "playstyle_tags"}
POSITIONS = ("guard", "wing", "big")
# all-around is left out: reviewers use it for "good at everything", not a style.
PLAYSTYLES = ("slasher", "shooter", "post", "defender", "speedster")

QUOTE_MUST_NAME = {
    "guard": re.compile(r"\bguards?\b", re.I),
    "wing": re.compile(r"\b(?:wings?|forwards?)\b", re.I),
    "big": re.compile(
        r"\b(?:bigs?|big m[ae]n|bigger players?|heavier|heavy players?|centers?|post players?)\b", re.I
    ),
    "slasher": re.compile(r"\b(?:slash\w*|drive\w*|attack\w* the rim)\b", re.I),
    "shooter": re.compile(r"\bshoot\w*\b", re.I),
    "post": re.compile(r"\b(?:post|paint)\b", re.I),
    "defender": re.compile(r"\b(?:defend\w*|defensive)\b", re.I),
    "speedster": re.compile(r"\b(?:quick|fast|shifty|speed\w*)\b", re.I),
}
RELEVANT = re.compile(
    r"\b(?:guards?|wings?|forwards?|bigs?|big m[ae]n|centers?|posts?|paint|positions?|heavier"
    r"|heavy players?|slashers?|shooters?|defenders?|speedsters?|quick players?|shifty"
    r"|recommend|ideal for|best for|great for|perfect for|suited)\b",
    re.I,
)
MAX_PASSAGES = 8
MAX_PASSAGE_CHARS = 700
WORKERS = 6

SYSTEM_PROMPT = """You tag basketball shoes using ONLY the review excerpts given.
Tag a position (guard, wing, big) or playstyle (slasher, shooter, post, defender, speedster) only when an excerpt says the shoe suits or is recommended for that kind of player, or clearly describes it as built for them.
Do not tag from a passing mention, from who endorses the shoe, from your own knowledge of the shoe, or when the excerpt says the shoe is NOT good for that player.
For every tag, copy a short exact quote from an excerpt that supports it. If nothing qualifies, return empty lists."""


def _tag_list(values: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"tag": {"type": "string", "enum": list(values)}, "quote": {"type": "string"}},
            "required": ["tag", "quote"],
            "additionalProperties": False,
        },
    }


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"positions": _tag_list(POSITIONS), "playstyles": _tag_list(PLAYSTYLES)},
    "required": ["positions", "playstyles"],
    "additionalProperties": False,
}


class JsonLLM(Protocol):
    def complete_json(
        self, *, system: str, user: str, schema_name: str, schema: dict[str, Any]
    ) -> dict[str, Any]: ...


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


def passages(shoe: dict[str, Any]) -> list[str]:
    """Review prose and pros/cons most likely to say who the shoe is for."""
    texts = [
        (item.get("text") or "").strip()
        for field in ("review_text", "pros", "cons")
        for item in shoe.get(field) or []
    ]
    relevant = [text for text in texts if text and RELEVANT.search(text)]
    return [text[:MAX_PASSAGE_CHARS] for text in relevant[:MAX_PASSAGES]]


def fingerprint(texts: list[str]) -> str:
    return hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()[:16]


def verified_tags(raw: dict[str, Any], texts: list[str]) -> dict[str, list[dict[str, str]]]:
    """Keep one quote per tag, only when it is verbatim and names that kind of player."""
    corpus = _fold(" ".join(texts))
    kept: dict[str, list[dict[str, str]]] = {kind: [] for kind in KINDS}
    for kind, allowed in (("positions", POSITIONS), ("playstyles", PLAYSTYLES)):
        seen: set[str] = set()
        for item in raw.get(kind) or []:
            tag, quote = item.get("tag"), (item.get("quote") or "").strip()
            if tag not in allowed or tag in seen or not quote:
                continue
            if _fold(quote) in corpus and QUOTE_MUST_NAME[tag].search(quote):
                kept[kind].append({"tag": tag, "quote": quote})
                seen.add(tag)
    return kept


def extract_one(shoe: dict[str, Any], llm: JsonLLM) -> dict[str, Any]:
    texts = passages(shoe)
    entry: dict[str, Any] = {"fingerprint": fingerprint(texts), "positions": [], "playstyles": []}
    if not texts:
        return entry
    excerpts = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(texts, 1))
    raw = llm.complete_json(
        system=SYSTEM_PROMPT,
        user=f"Shoe: {shoe['brand']} {shoe['model']}\n\nExcerpts:\n{excerpts}",
        schema_name="ShoeTags",
        schema=SCHEMA,
    )
    return {**entry, **verified_tags(raw, texts)}


def stale_shoes(canonical: list[dict[str, Any]], cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Shoes with no cached result, or whose review text changed since it was made."""
    return [
        shoe
        for shoe in canonical
        if (cache.get(shoe["canonical_id"]) or {}).get("fingerprint") != fingerprint(passages(shoe))
    ]


def update_cache(
    canonical: list[dict[str, Any]], cache: dict[str, Any], llm: JsonLLM
) -> tuple[dict[str, Any], int, int]:
    """Re-extract stale shoes and drop entries for shoes no longer scraped."""
    todo = stale_shoes(canonical, cache)
    failed = 0
    updated = {shoe["canonical_id"]: cache[shoe["canonical_id"]] for shoe in canonical if shoe["canonical_id"] in cache}

    def run(shoe: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        try:
            return shoe["canonical_id"], extract_one(shoe, llm)
        except Exception as exc:  # one bad response shouldn't sink the batch
            logger.warning("tag extraction failed for %s: %s", shoe["canonical_id"], exc)
            return shoe["canonical_id"], None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for canonical_id, entry in pool.map(run, todo):
            if entry is None:
                failed += 1
            else:
                updated[canonical_id] = entry
    return updated, len(todo), failed


def apply_review_tags(shoe: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    """Shoe dict with review tags added to the scraped ones (never removing any)."""
    entry = cache.get(shoe["canonical_id"])
    if not entry:
        return shoe
    merged = dict(shoe)
    for kind, field in KINDS.items():
        current = list(shoe.get(field) or [])
        merged[field] = current + [i["tag"] for i in entry[kind] if i["tag"] not in current]
    merged["review_tags"] = {kind: entry[kind] for kind in KINDS}
    return merged


def load_cache(path: Path = REVIEW_TAGS) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.tags.review_tags", description=__doc__)
    parser.add_argument("--staging", type=Path, default=CANONICAL)
    parser.add_argument("--out", type=Path, default=REVIEW_TAGS)
    parser.add_argument("--dry-run", action="store_true", help="count stale shoes; no API calls")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    canonical = json.loads(args.staging.read_text(encoding="utf-8"))
    cache = load_cache(args.out) or {}
    if args.dry_run:
        logger.info("dry run: %d of %d shoes need extraction", len(stale_shoes(canonical, cache)), len(canonical))
        return 0

    from shared.llm import get_llm_client

    updated, attempted, failed = update_cache(canonical, cache, get_llm_client())
    args.out.write_text(json.dumps(updated, indent=1, ensure_ascii=False), encoding="utf-8")
    tagged = sum(1 for entry in updated.values() if entry["positions"] or entry["playstyles"])
    logger.info(
        "extracted=%d failed=%d cached=%d shoes with review tags=%d -> %s",
        attempted - failed, failed, len(updated), tagged, args.out,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
