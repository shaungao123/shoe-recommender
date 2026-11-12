"""Saved quiz answers and the personal verdict for one shoe."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.recommend import get_embed_client
from app.db.repositories import preferences as preferences_repo
from app.db.repositories import shoes as shoes_repo
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.preferences import Preferences, PreferencesResponse, VerdictResponse
from app.services import verdict as verdict_service
from shared.db.models import User, UserPreferences
from shared.embedding import EmbeddingClient

router = APIRouter(prefix="/me", tags=["me"])


def _response(row: UserPreferences) -> PreferencesResponse:
    return PreferencesResponse(**Preferences(**row.answers).model_dump(), updated_at=row.updated_at)


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PreferencesResponse:
    row = preferences_repo.get_preferences(db, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No saved preferences")
    return _response(row)


@router.put("/preferences", response_model=PreferencesResponse)
def put_preferences(
    body: Preferences,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[EmbeddingClient, Depends(get_embed_client)],
) -> PreferencesResponse:
    row = preferences_repo.save_preferences(db, user.id, body)
    # Embed now so shoe pages never wait on the API; a failure retries on the next verdict.
    verdict_service.refresh_profile_vector(db, row, client)
    return _response(row)


@router.get("/verdict/{shoe_id}", response_model=VerdictResponse)
def get_verdict(
    shoe_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[EmbeddingClient, Depends(get_embed_client)],
) -> VerdictResponse:
    shoe = shoes_repo.get_shoe(db, shoe_id)
    if shoe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shoe not found")
    return verdict_service.verdict_for(db, user, shoe, client)
