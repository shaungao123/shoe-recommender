"""Orchestrates the RAG flow; falls back to constraint-ranked list on failure."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.schemas.recommend import RecommendRequest, RecommendResponse, RecommendedShoe
from app.services.rag import explainer
from app.services.ranking import select_top_candidates
from app.services.rag.retriever import retrieve, retrieve_fallback
from shared.embedding import EmbeddingClient, EmbeddingError

logger = logging.getLogger(__name__)

TOP_N = 3
# Larger than TOP_N so quiz answers have shoes to reorder before the cut to 3.
RANKING_POOL = 60
# Fallback scores are mostly ties, so a short pool would just be the lowest ids.
FALLBACK_POOL = 1000

_COURT_PHRASES = {
    "indoor": "Plays indoors.",
    "outdoor": "Plays outdoors on rough courts.",
    "both": "Plays both indoors and outdoors.",
}


def _shopper_profile(request: RecommendRequest) -> str:
    """The shopper's own words plus court and priorities, for search and explanations."""
    parts = [(request.playstyle or "").strip()]
    if request.court:
        parts.append(_COURT_PHRASES[request.court])
    if request.priorities:
        parts.append(f"Cares most about {' and '.join(request.priorities)}.")
    return " ".join(part for part in parts if part)


def recommend(
    session: Session,
    request: RecommendRequest,
    client: EmbeddingClient | None = None,
) -> RecommendResponse:
    """Retrieve candidates, fall back if needed, rank by the quiz, explain the top 3."""
    playstyle = _shopper_profile(request)
    aesthetic = (request.aesthetic or "").strip()
    has_semantic = bool(playstyle or aesthetic)
    filter_kwargs = dict(
        brand=request.brand,
        outdoor=request.outdoor,
        playstyle_tag=request.playstyle_tag,
        cut=request.cut,
        width=request.width,
        position=request.position,
    )

    candidates = []
    if has_semantic:
        try:
            candidates = retrieve(
                session,
                playstyle=playstyle,
                budget=request.budget,
                aesthetic=aesthetic,
                client=client,
                limit=RANKING_POOL,
                **filter_kwargs,
            )
        except EmbeddingError as exc:
            logger.warning("embedding failed; using fallback retrieval: %s", exc)

    if not candidates:
        candidates = retrieve_fallback(
            session,
            playstyle=playstyle,
            budget=request.budget,
            limit=FALLBACK_POOL,
            **filter_kwargs,
        )

    top = select_top_candidates(candidates, n=TOP_N, request=request)
    recommendations: list[RecommendedShoe] = explainer.explain(
        top, playstyle=playstyle, aesthetic=aesthetic
    )
    return RecommendResponse(recommendations=recommendations)
