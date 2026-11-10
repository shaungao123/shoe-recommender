"""GET/PATCH /me — authenticated profile."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repositories import users as users_repo
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.users import UserProfile, UserProfileUpdate
from shared.db.models import User

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserProfile)
def get_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("", response_model=UserProfile)
def patch_me(
    payload: UserProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    name = payload.display_name.strip() if payload.display_name else None
    if name == "":
        name = None
    return users_repo.update_display_name(db, user, name)
