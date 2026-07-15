"""Batch embeddings for corpus — same model as query-time.

    python -m pipeline.embed.embed_corpus              # embed the shoes table
    python -m pipeline.embed.embed_corpus --dry-run    # report chunk counts, no API calls

Reads the production ``shoes`` table (written by ``pipeline.upsert.writer``),
builds text chunks per shoe (a spec summary plus per-source review prose and
pros/cons), embeds them with the shared client, and makes the ``embeddings``
table match: unchanged chunks are kept as-is (never re-embedded), new chunks
are inserted, stale rows — including rows from an older embedding model —
are deleted. Idempotent; a re-run with no corpus changes makes zero API calls.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from shared.config import settings
from shared.db.models import Embedding, Shoe
from shared.embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# Keep chunks comfortably inside the model's context and the retrieval
# context budget; long review prose is split on paragraph boundaries.
MAX_CHUNK_CHARS = 1500

# Spec fields worth putting in the summary chunk, in display order.
_SUMMARY_SPECS = (
    ("cut_height", "{} cut"),
    ("cushioning_tech", "cushioning: {}"),
    ("traction_pattern", "traction: {}"),
    ("weight_oz", "weight: {} oz"),
    ("width_fit", "fit width: {}"),
    ("length_fit", "sizing: {}"),
    ("outdoor_suitability", "outdoor suitability: {}"),
)


@dataclass(frozen=True)
class Chunk:
    """One embeddable text unit for a shoe, with source provenance."""

    content: str
    source: str | None  # scrape source, or None for the synthesized spec summary


def build_spec_summary(shoe: Shoe) -> str:
    """One readable paragraph of structured facts — the 'what is this shoe' chunk."""
    specs: dict[str, Any] = shoe.specs or {}
    title = f"{shoe.brand} {shoe.name}"
    parts = [title]
    if specs.get("signature_player"):
        parts.append(f"signature shoe of {specs['signature_player']}")
    if specs.get("release_year"):
        parts.append(f"released {specs['release_year']}")
    for field, template in _SUMMARY_SPECS:
        value = specs.get(field)
        if value is not None:
            text = str(value).replace("_", " ")
            parts.append(template.format(text))
    if specs.get("position_tags"):
        parts.append("positions: " + ", ".join(specs["position_tags"]))
    if specs.get("playstyle_tags"):
        parts.append("playstyles: " + ", ".join(specs["playstyle_tags"]))
    parts.append(f"price: ${shoe.price:.0f}")
    return ". ".join(parts) + "."


def _split_long(text: str) -> list[str]:
    """Split prose over MAX_CHUNK_CHARS on paragraph, then sentence, boundaries.

    Nothing is dropped: an oversized paragraph recurses into sentence splits,
    and a run with no boundaries at all is sliced into full-size windows.
    """
    text = text.strip()
    if len(text) <= MAX_CHUNK_CHARS:
        return [text] if text else []
    for joiner in ("\n\n", ". "):
        if joiner not in text:
            continue
        pieces: list[str] = []
        current = ""
        for part in text.split(joiner):
            candidate = f"{current}{joiner}{part}" if current else part
            if len(candidate) > MAX_CHUNK_CHARS and current:
                pieces.extend(_split_long(current))
                current = part
            else:
                current = candidate
        if current:
            pieces.extend(_split_long(current))
        return pieces
    # no paragraph or sentence boundaries at all: slice into windows
    return [text[i : i + MAX_CHUNK_CHARS] for i in range(0, len(text), MAX_CHUNK_CHARS)]


def _grouped_by_source(items: list[dict[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in items or []:
        text = (item.get("text") or "").strip()
        if text:
            grouped.setdefault(item.get("source") or "unknown", []).append(text)
    return grouped


def build_chunks(shoe: Shoe) -> list[Chunk]:
    """All embeddable chunks for one shoe: spec summary, reviews, pros/cons."""
    meta: dict[str, Any] = shoe.extra_metadata or {}
    title = f"{shoe.brand} {shoe.name}"
    chunks: list[Chunk] = [Chunk(content=build_spec_summary(shoe), source=None)]

    for source, segments in _grouped_by_source(meta.get("review_text", [])).items():
        for segment in segments:
            for piece in _split_long(segment):
                chunks.append(Chunk(content=f"{title} — {piece}", source=source))

    pros = _grouped_by_source(meta.get("pros", []))
    cons = _grouped_by_source(meta.get("cons", []))
    for source in sorted(set(pros) | set(cons)):
        lines = [title]
        if source in pros:
            lines.append("Pros: " + "; ".join(pros[source]))
        if source in cons:
            lines.append("Cons: " + "; ".join(cons[source]))
        for piece in _split_long("\n".join(lines)):
            chunks.append(Chunk(content=piece, source=source))

    # dedupe repeated segments, preserving order. Keyed by (content, source)
    # — identical text from two sources stays as two chunks so each keeps its
    # own provenance for source-credited explanations.
    return list({(c.content, c.source): c for c in chunks}.values())


@dataclass
class SyncResult:
    shoes: int = 0
    kept: int = 0
    embedded: int = 0
    deleted: int = 0


def sync_embeddings(
    session: Session, client: EmbeddingClient, dry_run: bool = False
) -> SyncResult:
    """Make the embeddings table match the current corpus. Caller commits.

    A dry run only counts — it stages no inserts or deletes, so committing
    after one is a no-op. Chunks are identified by (content, source): the
    same text re-attributed to a different source is re-embedded so the
    stored provenance stays truthful.
    """
    result = SyncResult()
    to_embed: list[tuple[int, Chunk]] = []  # (shoe_id, chunk)
    stale: list[Embedding] = []

    existing_by_shoe: dict[int, list[Embedding]] = {}
    for row in session.scalars(select(Embedding)):
        existing_by_shoe.setdefault(row.shoe_id, []).append(row)

    for shoe in session.scalars(select(Shoe)):
        result.shoes += 1
        desired = {(chunk.content, chunk.source): chunk for chunk in build_chunks(shoe)}

        for row in existing_by_shoe.get(shoe.id, []):
            key = (row.content, row.source)
            if row.model_id == client.model_id and key in desired:
                desired.pop(key)
                result.kept += 1
            else:
                stale.append(row)
                result.deleted += 1

        to_embed.extend((shoe.id, chunk) for chunk in desired.values())

    result.embedded = len(to_embed)
    if dry_run:
        return result

    for row in stale:
        session.delete(row)
    if not to_embed:
        return result

    vectors = client.embed([chunk.content for _, chunk in to_embed])
    for (shoe_id, chunk), vector in zip(to_embed, vectors, strict=True):
        session.add(
            Embedding(
                shoe_id=shoe_id,
                content=chunk.content,
                source=chunk.source,
                model_id=client.model_id,
                vector=vector,
            )
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline.embed.embed_corpus", description=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build chunks and report counts; no API calls, no writes",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if settings.database_url.startswith("sqlite"):
        logger.error(
            "database_url is the SQLite fallback — set the Postgres URL in "
            "backend/.env (pgvector requires Postgres)"
        )
        return 1

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    client = EmbeddingClient()
    with Session(engine) as session:
        result = sync_embeddings(session, client, dry_run=args.dry_run)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    logger.info(
        "%sshoes=%d kept=%d embedded=%d deleted=%d (model=%s)",
        "dry run: " if args.dry_run else "",
        result.shoes,
        result.kept,
        result.embedded,
        result.deleted,
        client.model_id,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
