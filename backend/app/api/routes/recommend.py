"""POST /recommend — accept playstyle, budget, aesthetic; return top-3."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services import recommend as recommend_service
from shared.embedding import EmbeddingClient, get_embedding_client

router = APIRouter(prefix="/recommend", tags=["recommend"])


def get_embed_client() -> EmbeddingClient:
    return get_embedding_client()


@router.post("", response_model=RecommendResponse)
def post_recommend(
    body: RecommendRequest,
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[EmbeddingClient, Depends(get_embed_client)],
) -> RecommendResponse:
    return recommend_service.recommend(db, body, client=client)
