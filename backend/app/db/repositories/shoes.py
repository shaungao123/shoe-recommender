"""Shoe queries: browse filters, vector search, candidate retrieval.

Hard filters run in SQL first (price is a real indexed column), then pgvector
ranks the survivors' chunks by cosine distance — one round trip for the chunk
query, one to load the shoe rows. If we ever outgrow pgvector, this module and
the retriever are the only things that should change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from shared.db.models import Embedding, Shoe

# How many chunks past limit*snippets_per_shoe the top-k query over-fetches.
# The single ORDER BY distance LIMIT n query is what lets Postgres use the
# HNSW index; the price we pay is that a top shoe's lower-ranked snippets can
# fall outside the window when many shoes cluster near the query — snippet
# lists then come back shorter, which degrades gracefully.
OVERFETCH_FACTOR = 4


@dataclass
class ChunkHit:
    content: str
    source: str | None
    distance: float  # cosine distance, lower = better


@dataclass
class ShoeMatch:
    """One shoe that survived the filters, with its best-matching chunks."""

    shoe: Shoe
    distance: float  # best chunk's cosine distance
    chunks: list[ChunkHit] = field(default_factory=list)


def _json_str(shoe_col, key: str):
    """Scalar JSON field as text — works on SQLite and Postgres."""
    return shoe_col[key].as_string()


def _json_array_contains(shoe_col, key: str, value: str):
    """True when a JSON string-array field contains ``value``.

    Portable across SQLite (tests) and Postgres: match the quoted token in
    the serialized array. Fine for a small shoe corpus.
    """
    return cast(shoe_col[key], String).like(f'%"{value}"%')


def _apply_filters(
    stmt,
    *,
    brand: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    outdoor: str | None = None,
    playstyle: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
):
    if brand is not None:
        stmt = stmt.where(func.lower(Shoe.brand) == brand.lower())
    if budget_min is not None:
        stmt = stmt.where(Shoe.price >= budget_min)
    if budget_max is not None:
        stmt = stmt.where(Shoe.price <= budget_max)
    if outdoor is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "outdoor_suitability") == outdoor)
    if cut is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "cut_height") == cut)
    if width is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "width_fit") == width)
    if playstyle is not None:
        stmt = stmt.where(_json_array_contains(Shoe.specs, "playstyle_tags", playstyle))
    if position is not None:
        stmt = stmt.where(_json_array_contains(Shoe.specs, "position_tags", position))
    return stmt


def list_shoes(
    session: Session,
    *,
    brand: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    outdoor: str | None = None,
    playstyle: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Shoe], int]:
    """Return matching shoes (price asc, then name) and total match count."""
    filters = dict(
        brand=brand,
        budget_min=budget_min,
        budget_max=budget_max,
        outdoor=outdoor,
        playstyle=playstyle,
        cut=cut,
        width=width,
        position=position,
    )
    base = _apply_filters(select(Shoe), **filters)
    total = session.scalar(
        _apply_filters(select(func.count()).select_from(Shoe), **filters)
    ) or 0
    rows = list(
        session.scalars(
            base.order_by(Shoe.price.asc(), Shoe.name.asc()).limit(limit).offset(offset)
        )
    )
    return rows, total


def get_shoe(session: Session, shoe_id: int) -> Shoe | None:
    return session.get(Shoe, shoe_id)


def search_candidates(
    session: Session,
    query_vector: list[float],
    model_id: str,
    max_price: float | None = None,
    limit: int = 10,
    snippets_per_shoe: int = 3,
) -> list[ShoeMatch]:
    """Budget-filtered pgvector search; shoes ranked by their best chunk."""
    distance = Embedding.vector.cosine_distance(query_vector).label("distance")

    chunk_query = (
        select(Embedding.shoe_id, Embedding.content, Embedding.source, distance)
        .join(Shoe, Shoe.id == Embedding.shoe_id)
        .where(Embedding.model_id == model_id)
        .order_by(distance)
        .limit(limit * snippets_per_shoe * OVERFETCH_FACTOR)
    )
    if max_price is not None:
        chunk_query = chunk_query.where(Shoe.price <= max_price)

    hits_by_shoe: dict[int, list[ChunkHit]] = {}
    for row in session.execute(chunk_query):  # ordered best-first
        hits = hits_by_shoe.setdefault(row.shoe_id, [])
        if len(hits) < snippets_per_shoe:
            hits.append(
                ChunkHit(content=row.content, source=row.source, distance=row.distance)
            )

    top_ids = list(hits_by_shoe)[:limit]  # insertion order = best-chunk order
    if not top_ids:
        return []
    shoes = {
        shoe.id: shoe
        for shoe in session.scalars(select(Shoe).where(Shoe.id.in_(top_ids)))
    }
    return [
        ShoeMatch(
            shoe=shoes[shoe_id],
            distance=hits_by_shoe[shoe_id][0].distance,
            chunks=hits_by_shoe[shoe_id],
        )
        for shoe_id in top_ids
    ]


def list_shoes_within_budget(
    session: Session, max_price: float | None = None, limit: int | None = None
) -> list[Shoe]:
    """No-vector fallback pool: budget filter only, priciest first.

    The retriever re-ranks this in Python (playstyle tag overlap); the corpus
    is small enough that pulling every in-budget row is fine.
    """
    query = select(Shoe).order_by(Shoe.price.desc(), Shoe.id)
    if max_price is not None:
        query = query.where(Shoe.price <= max_price)
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))
