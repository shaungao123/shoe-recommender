"""Upsert structured shoe rows and vectors to Postgres.

    python -m pipeline.upsert.writer                 # write staging/canonical.json
    python -m pipeline.upsert.writer --dry-run       # report counts, roll back
    python -m pipeline.upsert.writer --staging PATH  # alternate corpus file

Review tags from ``pipeline.tags.review_tags`` (``staging/review_tags.json``)
are merged into the scraped tags before writing. The writer refuses to run
without that file unless ``--without-review-tags`` is passed, because writing
the scrape alone would silently drop them.

Shoes that are on a wishlist or have feedback are never deleted silently: the
writer stops and names them unless ``--allow-deleting-referenced`` is passed.

Reads the staging corpus produced by ``pipeline.run`` and makes the ``shoes``
table match it: upserts by ``canonical_id``, then deletes every row that is
not in the batch — including rows with no ``canonical_id`` at all (pre-pipeline
mock data). Run explicitly, never as part of the scrape run. Embedding vectors
are a separate later step (``pipeline.embed``).

``image_url`` and ``extra_metadata.image_search`` are owned by
``pipeline.images.search``, not the scrape. New rows start with a null image;
updates keep whatever photo that script already saved.
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

from pipeline.tags.review_tags import apply_review_tags, load_cache
from shared.config import settings
from shared.db.models import Feedback, Shoe, WishlistItem

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
# Photos are filled by ``pipeline.images.search``; do not write scraped URLs.
METADATA_FIELDS = (
    "metrics",
    "pros",
    "cons",
    "review_text",
    "provenance",
    "sources",
    "review_tags",  # quote behind each review-extracted tag, for citations
)


class ReferencedShoesError(RuntimeError):
    """Deleting these shoes would remove users' wishlist items or orphan feedback."""


@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


def load_canonical(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def shoe_values_from_canonical(shoe: dict[str, Any]) -> dict[str, Any]:
    """Map a CanonicalShoe dict to Shoe column values.

    ``image_url`` is always null here — the image search command owns that
    column. Callers that update an existing row must preserve the prior value.
    """
    msrp_cents = shoe.get("msrp_usd_cents")
    if msrp_cents is None:
        # price is nullable — the budget hard-filter (price <= max) simply
        # never matches these rows, so they're stored but not recommended
        # until a source supplies MSRP.
        logger.warning("no MSRP for %s: storing with price=null", shoe.get("canonical_id"))
    sources = shoe.get("sources") or []
    return {
        "canonical_id": shoe["canonical_id"],
        "brand": shoe["brand"],
        "name": shoe["model"],
        "price": Decimal(msrp_cents) / 100 if msrp_cents is not None else None,
        "currency": "USD",
        "image_url": None,
        "affiliate_url": None,  # populated by the future affiliate-feed step
        "source_url": sources[0]["url"] if sources else None,
        "specs": {f: shoe.get(f) for f in SPEC_FIELDS},
        "extra_metadata": {f: shoe.get(f) for f in METADATA_FIELDS},
    }


def _referenced_shoes(session: Session, shoe_ids: list[int]) -> list[Shoe]:
    if not shoe_ids:
        return []
    referenced = set(
        session.scalars(select(WishlistItem.shoe_id).where(WishlistItem.shoe_id.in_(shoe_ids)))
    ) | set(session.scalars(select(Feedback.shoe_id).where(Feedback.shoe_id.in_(shoe_ids))))
    return list(session.scalars(select(Shoe).where(Shoe.id.in_(referenced)))) if referenced else []


def upsert_shoes(
    session: Session,
    canonical: list[dict[str, Any]],
    allow_deleting_referenced: bool = False,
) -> UpsertResult:
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
            # Photos are owned by pipeline.images.search — keep them.
            values["image_url"] = row.image_url
            prior_search = (row.extra_metadata or {}).get("image_search")
            if prior_search is not None:
                values["extra_metadata"] = {
                    **values["extra_metadata"],
                    "image_search": prior_search,
                }
            changed = False
            for field, value in values.items():
                if getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
            result.updated += changed

    is_stale = or_(Shoe.canonical_id.is_(None), Shoe.canonical_id.not_in(seen))
    stale_ids = list(session.scalars(select(Shoe.id).where(is_stale)))
    referenced = _referenced_shoes(session, stale_ids)
    if referenced and not allow_deleting_referenced:
        names = ", ".join(f"{shoe.brand} {shoe.name}" for shoe in referenced)
        raise ReferencedShoesError(
            f"{len(referenced)} shoe(s) missing from this batch are on wishlists or have "
            f"feedback: {names}"
        )
    result.deleted = session.execute(delete(Shoe).where(is_stale)).rowcount
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
    parser.add_argument(
        "--without-review-tags",
        action="store_true",
        help="write without staging/review_tags.json (drops review-extracted tags)",
    )
    parser.add_argument(
        "--allow-deleting-referenced",
        action="store_true",
        help="delete shoes even if they are on wishlists or have feedback",
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
    review_tags = load_cache(args.staging.parent / "review_tags.json")
    if review_tags is None and not args.without_review_tags:
        logger.error(
            "no review_tags.json next to %s — run `python -m pipeline.tags.review_tags` "
            "first, or pass --without-review-tags to drop those tags",
            args.staging,
        )
        return 1
    canonical = [apply_review_tags(shoe, review_tags or {}) for shoe in canonical]

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with Session(engine) as session:
        try:
            result = upsert_shoes(
                session, canonical, allow_deleting_referenced=args.allow_deleting_referenced
            )
        except ReferencedShoesError as exc:
            session.rollback()
            logger.error("%s — nothing written", exc)
            return 1
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
