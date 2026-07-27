"""pgvector search with hard filters (budget, constraints).

The retrieval half of RAG: user inputs → SQL hard-filters on shoes →
pgvector similarity over review/spec chunks → small ranked Candidate list
(top ~10) for the explainer to choose 3 from. ``retrieve_fallback`` is the
no-vector path for when embedding or the vector query fails — the service
layer decides when to use it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.repositories.shoes import ShoeMatch, list_filtered_shoes, search_candidates
from app.schemas.candidate import Candidate, ReviewSnippet
from app.services.rag.embedder import embed_query
from shared.config import settings
from shared.db.models import Shoe
from shared.embedding import EmbeddingClient
from shared.tags import extract_tags

DEFAULT_LIMIT = 10
SNIPPETS_PER_SHOE = 3


def build_query_text(playstyle: str, aesthetic: str) -> str:
    """Text to embed — mirrors corpus register; handles playstyle-only or aesthetic-only."""
    playstyle = playstyle.strip()
    aesthetic = aesthetic.strip()
    parts: list[str] = []
    if playstyle:
        parts.append(f"Basketball shoe for a {playstyle} player.")
    if aesthetic:
        parts.append(f"Style and look: {aesthetic}.")
    if parts:
        return " ".join(parts)
    return "Basketball shoe recommendation."


def _filter_kwargs(
    *,
    budget: float | None = None,
    brand: str | None = None,
    outdoor: str | None = None,
    playstyle_tag: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
) -> dict[str, Any]:
    return dict(
        brand=brand,
        budget_max=budget,
        outdoor=outdoor,
        playstyle=playstyle_tag,
        cut=cut,
        width=width,
        position=position,
    )


def retrieve(
    session: Session,
    playstyle: str,
    budget: float | None,
    aesthetic: str,
    client: EmbeddingClient | None = None,
    limit: int = DEFAULT_LIMIT,
    *,
    brand: str | None = None,
    outdoor: str | None = None,
    playstyle_tag: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
) -> list[Candidate]:
    """Ranked candidates for the explainer. Raises EmbeddingError if the
    embeddings API fails — callers fall back to ``retrieve_fallback``."""
    query_vector = embed_query(build_query_text(playstyle, aesthetic), client=client)
    matches = search_candidates(
        session,
        query_vector,
        model_id=client.model_id if client else settings.embedding_model_id,
        limit=limit,
        snippets_per_shoe=SNIPPETS_PER_SHOE,
        **_filter_kwargs(
            budget=budget,
            brand=brand,
            outdoor=outdoor,
            playstyle_tag=playstyle_tag,
            cut=cut,
            width=width,
            position=position,
        ),
    )
    return [_to_candidate(match) for match in matches]


def retrieve_fallback(
    session: Session,
    playstyle: str,
    budget: float | None,
    limit: int = DEFAULT_LIMIT,
    *,
    brand: str | None = None,
    outdoor: str | None = None,
    playstyle_tag: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
) -> list[Candidate]:
    """Constraint-ranked list, no vectors: hard filters in SQL, then rank by
    playstyle/position tag overlap with the user's own words."""
    shoes = list_filtered_shoes(
        session,
        **_filter_kwargs(
            budget=budget,
            brand=brand,
            outdoor=outdoor,
            playstyle_tag=playstyle_tag,
            cut=cut,
            width=width,
            position=position,
        ),
    )
    scored = sorted(
        ((_tag_overlap(playstyle, shoe), shoe.id, shoe) for shoe in shoes),
        key=lambda item: (-item[0], item[1]),
    )
    return [
        _shoe_to_candidate(shoe, tag_overlap=overlap)
        for overlap, _, shoe in scored[:limit]
    ]


def _tag_overlap(playstyle: str, shoe: Shoe) -> int:
    """Canonical tags the user's own words share with the shoe's tags.

    Goes through shared/tags.py so the fallback understands the same synonym
    vocabulary the pipeline indexed with ("shifty" → speedster, "pg" → guard).
    """
    specs = shoe.specs or {}
    tags = set(specs.get("playstyle_tags") or []) | set(specs.get("position_tags") or [])
    return len(tags & extract_tags(playstyle))


def _to_candidate(match: ShoeMatch) -> Candidate:
    candidate = _shoe_to_candidate(match.shoe)
    candidate.snippets = [
        ReviewSnippet(text=chunk.content, source=chunk.source) for chunk in match.chunks
    ]
    candidate.similarity = max(0.0, 1.0 - match.distance)
    return candidate


def _shoe_to_candidate(shoe: Shoe, *, tag_overlap: int | None = None) -> Candidate:
    return Candidate(
        shoe_id=shoe.id,
        canonical_id=shoe.canonical_id,
        brand=shoe.brand,
        name=shoe.name,
        price=float(shoe.price),
        currency=shoe.currency,
        image_url=shoe.image_url,
        affiliate_url=shoe.affiliate_url,
        specs=shoe.specs or {},
        tag_overlap=tag_overlap,
    )
