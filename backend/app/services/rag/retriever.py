"""pgvector search with hard filters (budget, constraints).

The retrieval half of RAG: user inputs → budget hard-filter in SQL →
pgvector similarity over review/spec chunks → small ranked Candidate list
(top ~10) for the explainer to choose 3 from. ``retrieve_fallback`` is the
no-vector path for when embedding or the vector query fails — the service
layer decides when to use it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.shoes import ShoeMatch, list_shoes_within_budget, search_candidates
from app.schemas.candidate import Candidate, ReviewSnippet
from app.services.rag.embedder import embed_query
from shared.config import settings
from shared.db.models import Shoe
from shared.embedding import EmbeddingClient
from shared.tags import extract_tags

DEFAULT_LIMIT = 10
SNIPPETS_PER_SHOE = 3


def build_query_text(playstyle: str, aesthetic: str) -> str:
    """The text we embed for a request — mirrors the corpus chunks' register."""
    parts = [f"Basketball shoe for a {playstyle.strip()} player."]
    if aesthetic.strip():
        parts.append(f"Style and look: {aesthetic.strip()}.")
    return " ".join(parts)


def retrieve(
    session: Session,
    playstyle: str,
    budget: float,
    aesthetic: str,
    client: EmbeddingClient | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    """Ranked candidates for the explainer. Raises EmbeddingError if the
    embeddings API fails — callers fall back to ``retrieve_fallback``."""
    query_vector = embed_query(build_query_text(playstyle, aesthetic), client=client)
    matches = search_candidates(
        session,
        query_vector,
        model_id=client.model_id if client else settings.embedding_model_id,
        max_price=budget,
        limit=limit,
        snippets_per_shoe=SNIPPETS_PER_SHOE,
    )
    return [_to_candidate(match) for match in matches]


def retrieve_fallback(
    session: Session,
    playstyle: str,
    budget: float,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    """Constraint-ranked list, no vectors: budget filter in SQL, then rank by
    playstyle/position tag overlap with the user's own words."""
    shoes = list_shoes_within_budget(session, max_price=budget)
    scored = sorted(
        ((_tag_overlap(playstyle, shoe), i, shoe) for i, shoe in enumerate(shoes)),
        key=lambda item: (-item[0], item[1]),  # ties keep budget (price desc) order
    )
    return [_shoe_to_candidate(shoe) for _, _, shoe in scored[:limit]]


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
    # cosine distance -> similarity, clamped to [0, 1] for the rare >1
    # distance. None (the fallback marker) is reserved for no-vector paths.
    candidate.similarity = max(0.0, 1.0 - match.distance)
    return candidate


def _shoe_to_candidate(shoe: Shoe) -> Candidate:
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
    )
