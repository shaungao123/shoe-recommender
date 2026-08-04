"""Upsert structured shoe rows and vectors to Postgres.

    python -m pipeline.upsert.writer                 # write staging/canonical.json
    python -m pipeline.upsert.writer --dry-run       # report counts, roll back
    python -m pipeline.upsert.writer --staging PATH  # alternate corpus file

Reads the staging corpus produced by ``pipeline.run`` and makes the ``shoes``
table match it: upserts by ``canonical_id``, then deletes every row that is
not in the batch — including rows with no ``canonical_id`` at all (pre-pipeline
mock data). Run explicitly, never as part of the scrape run. Embedding vectors
are a separate later step (``pipeline.embed``).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.orm import Session

from shared.config import settings
from shared.db.models import Shoe

logger = logging.getLogger(__name__)

STAGING_CANONICAL = Path(__file__).resolve().parent.parent / "staging" / "canonical.json"

# CanonicalShoe fields that land in the `specs` JSON column.
SPEC_FIELDS = (
    "version",
    "release_year",
    "signature_player",
    "weight_oz",
    "weight_g",
    "drop_mm",
    "stack_heel_mm",
    "stack_forefoot_mm",
    "cut_height",
    "width_fit",
    "length_fit",
    "cushioning_tech",
    "traction_pattern",
    "outdoor_suitability",
    "position_tags",
    "playstyle_tags",
)

# Everything provenance/review-shaped goes to `extra_metadata`. `metrics`
# stays keyed per source — scores are never averaged across sources.
METADATA_FIELDS = (
    "metrics",
    "pros",
    "cons",
    "review_text",
    "provenance",
    "sources",
    "image_urls",
)


@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


def load_canonical(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def shoe_values_from_canonical(shoe: dict[str, Any]) -> dict[str, Any]:
    """Map a CanonicalShoe dict to Shoe column values."""
    msrp_cents = shoe.get("msrp_usd_cents")
    if msrp_cents is None:
        # price is nullable — the budget hard-filter (price <= max) simply
        # never matches these rows, so they're stored but not recommended
        # until a source supplies MSRP.
        logger.warning("no MSRP for %s: storing with price=null", shoe.get("canonical_id"))
    image_urls = shoe.get("image_urls") or []
    sources = shoe.get("sources") or []
    return {
        "canonical_id": shoe["canonical_id"],
        "brand": shoe["brand"],
        "name": shoe["model"],
        "price": Decimal(msrp_cents) / 100 if msrp_cents is not None else None,
        "currency": "USD",
        "image_url": image_urls[0] if image_urls else None,
        "affiliate_url": None,  # populated by the future affiliate-feed step
        "source_url": sources[0]["url"] if sources else None,
        "specs": {f: shoe.get(f) for f in SPEC_FIELDS},
        "extra_metadata": {f: shoe.get(f) for f in METADATA_FIELDS},
    }


def upsert_shoes(session: Session, canonical: list[dict[str, Any]]) -> UpsertResult:
    """Make the shoes table match the canonical batch. Caller commits."""
    result = UpsertResult()
    existing = {
        row.canonical_id: row
        for row in session.scalars(select(Shoe).where(Shoe.canonical_id.is_not(None)))
    }

    seen: set[str] = set()
    for shoe in canonical:
        values = shoe_values_from_canonical(shoe)
        seen.add(values["canonical_id"])
        row = existing.get(values["canonical_id"])
        if row is None:
            session.add(Shoe(**values))
            result.inserted += 1
        else:
            changed = False
            for field, value in values.items():
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            result.updated += changed

    stale = delete(Shoe).where(
        or_(Shoe.canonical_id.is_(None), Shoe.canonical_id.not_in(seen))
    )
    result.deleted = session.execute(stale).rowcount
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.upsert.writer", description=__doc__)
    parser.add_argument(
        "--staging",
        type=Path,
        default=STAGING_CANONICAL,
        help=f"canonical corpus JSON (default: {STAGING_CANONICAL})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="compute and report counts, then roll back"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if settings.database_url.startswith("sqlite"):
        logger.error(
            "database_url is the SQLite fallback (%s) — set the Postgres URL "
            "in backend/.env before writing the corpus",
            settings.database_url,
        )
        return 1

    canonical = load_canonical(args.staging)
    logger.info("loaded %d canonical shoes from %s", len(canonical), args.staging)

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with Session(engine) as session:
        result = upsert_shoes(session, canonical)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    logger.info(
        "%sinserted=%d updated=%d deleted=%d",
        "dry run (rolled back): " if args.dry_run else "",
        result.inserted,
        result.updated,
        result.deleted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
