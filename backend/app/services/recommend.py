"""Orchestrates the RAG flow; falls back to constraint-ranked list on failure."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.schemas.recommend import RecommendRequest, RecommendResponse, RecommendedShoe
from app.services.rag import explainer
from app.services.ranking import request_seed, select_top_candidates
from app.services.rag.retriever import retrieve, retrieve_fallback
from shared.embedding import EmbeddingClient, EmbeddingError

logger = logging.getLogger(__name__)

TOP_N = 3


def recommend(
    session: Session,
    request: RecommendRequest,
    client: EmbeddingClient | None = None,
) -> RecommendResponse:
    """Retrieve candidates, fall back if needed, pick top 3, explain."""
    playstyle = (request.playstyle or "").strip()
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
                **filter_kwargs,
            )
        except EmbeddingError as exc:
            logger.warning("embedding failed; using fallback retrieval: %s", exc)

    if not candidates:
        candidates = retrieve_fallback(
            session,
            playstyle=playstyle,
            budget=request.budget,
            **filter_kwargs,
        )

    top = select_top_candidates(candidates, n=TOP_N, seed=request_seed(request))
    recommendations: list[RecommendedShoe] = explainer.explain(
        top, playstyle=playstyle
    )
    return RecommendResponse(recommendations=recommendations)
