"""FastAPI dependency injection (DB sessions, auth)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.supabase import verify_access_token
from app.db.repositories import users as users_repo
from app.db.session import get_db as _get_db
from shared.db.models import User

GetDbDep = Generator[Session, None, None]

_bearer = HTTPBearer(auto_error=False)


def get_db() -> GetDbDep:
    yield from _get_db()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(_get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = verify_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return users_repo.upsert_from_claims(
        db,
        user_id=claims.user_id,
        email=claims.email,
        display_name=claims.display_name,
    )
