"""Pipeline CLI — scrape sources, resolve entities, write the staging corpus.

    python -m pipeline.run                      # all sources, full crawl
    python -m pipeline.run --source runrepeat   # one source only
    python -m pipeline.run --limit 10           # cap detail fetches per source
    python -m pipeline.run --pilot              # ~30-shoe cross-source corpus
    python -m pipeline.run --refresh            # ignore the HTML cache

Output goes to ``pipeline/staging/`` (JSON), never to the production shoes
table. Embeddings and live prices are separate, later steps.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from pipeline.normalize import model_key, resolve, split_brand
from pipeline.schema import MERGEABLE_FIELDS, SourceRecord
from pipeline.scrapers import Fetcher, get_scrapers
from pipeline.scrapers.base import ShoeRef

STAGING_DIR = Path(__file__).resolve().parent / "staging"

# Pilot: prove cross-source merging on a small corpus. The two spec/lab
# sources are crawled first; the two big aggregator sites are then fetched
# ONLY for shoes we already saw, so we never hammer them for shoes that
# can't produce a >=2-source record.
PILOT_SEED_LIMITS = {"basketballshoespecs": 50, "runrepeat": 40}
PILOT_FOLLOW_CAP = 60
PILOT_TARGET = 30


def _ref_key(ref: ShoeRef) -> tuple[str | None, str]:
    brand, model = split_brand(ref.name)
    return brand, model_key(brand, model)


def scrape_sources(
    sources: list[str],
    fetcher: Fetcher,
    limit: int | None,
    pilot: bool,
) -> list[SourceRecord]:
    scrapers = get_scrapers()
    records: list[SourceRecord] = []
    seed_keys: set[str] = set()

    for name in sources:
        scraper = scrapers[name](fetcher)
        if pilot:
            if name in PILOT_SEED_LIMITS:
                batch = scraper.scrape(limit=PILOT_SEED_LIMITS[name])
                seed_keys.update(
                    model_key(r.brand, r.model or r.model_raw) for r in batch
                )
            else:
                batch = scraper.scrape(
                    limit=PILOT_FOLLOW_CAP,
                    ref_filter=lambda ref: _ref_key(ref)[1] in seed_keys,
                )
        else:
            batch = scraper.scrape(limit=limit)
        records.extend(batch)
        _write_json(STAGING_DIR / f"records_{name}.json", [r.to_dict() for r in batch])
    return records


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8"
    )


def coverage_report(canonical, records, unmatched, ambiguous) -> str:
    lines = ["", "=" * 62, "COVERAGE REPORT", "=" * 62]

    by_source = Counter(r.source for r in records)
    lines.append(f"per-source records parsed: {dict(by_source)}")

    lines.append(f"canonical shoes: {len(canonical)}")
    source_counts = Counter(len(shoe.sources) for shoe in canonical)
    for n in sorted(source_counts, reverse=True):
        lines.append(f"  in {n} source(s): {source_counts[n]}")
    multi = sum(1 for s in canonical if len(s.sources) >= 2)
    lines.append(f"  cross-source (>=2): {multi}")

    lines.append("field fill rates (canonical):")
    fields = list(MERGEABLE_FIELDS) + ["position_tags", "playstyle_tags"]
    for field_name in fields:
        filled = sum(
            1 for s in canonical if getattr(s, field_name) not in (None, [], {})
        )
        pct = 100 * filled / len(canonical) if canonical else 0
        lines.append(f"  {field_name:22} {filled:4}/{len(canonical)}  ({pct:3.0f}%)")
    for container in ("metrics", "pros", "review_text", "image_urls"):
        filled = sum(1 for s in canonical if getattr(s, container))
        lines.append(f"  {container:22} {filled:4}/{len(canonical)}")

    lines.append(f"unmatched (manual review): {len(unmatched)}")
    lines.append(f"ambiguous near-misses (manual review): {len(ambiguous)}")
    lines.append("=" * 62)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.run", description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(get_scrapers()),
        help="scrape only this source (repeatable); default: all",
    )
    parser.add_argument("--limit", type=int, help="max detail pages per source")
    parser.add_argument(
        "--pilot",
        action="store_true",
        help=f"build a ~{PILOT_TARGET}-shoe corpus of shoes seen in >=2 sources",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="re-fetch even if cached"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    order = ["basketballshoespecs", "runrepeat", "thehoopsgeek", "weartesters"]
    sources = args.source or sorted(get_scrapers(), key=order.index)
    fetcher = Fetcher(refresh=args.refresh)
    records = scrape_sources(sources, fetcher, args.limit, args.pilot)

    report = resolve(records)
    canonical = report.canonical
    if args.pilot:
        # keep the shoes with the best cross-source coverage
        canonical = [s for s in canonical if len(s.sources) >= 2]
        canonical.sort(
            key=lambda s: (
                -len(s.sources),
                -sum(1 for f in MERGEABLE_FIELDS if getattr(s, f) is not None),
            )
        )
        canonical = canonical[:PILOT_TARGET]

    _write_json(STAGING_DIR / "canonical.json", [s.to_dict() for s in canonical])
    _write_json(STAGING_DIR / "unmatched.json", report.unmatched)
    _write_json(STAGING_DIR / "ambiguous.json", report.ambiguous)

    print(coverage_report(canonical, records, report.unmatched, report.ambiguous))
    print(f"staging output: {STAGING_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
