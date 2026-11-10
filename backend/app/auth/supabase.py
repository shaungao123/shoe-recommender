"""Verify Supabase Auth access tokens via the project's JWKS."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient

from shared.config import settings

_ALGORITHMS = ("RS256", "ES256")


@dataclass(frozen=True)
class AuthClaims:
    user_id: UUID
    email: str
    display_name: str | None


@lru_cache(maxsize=1)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    base = supabase_url.rstrip("/")
    return PyJWKClient(
        f"{base}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
    )


def _display_name_from_metadata(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("display_name", "full_name", "name"):
        value = metadata.get(key)
        if isinstance(value, str):
            name = value.strip()
            if name:
                return name[:80]
    return None


def verify_access_token(token: str) -> AuthClaims:
    """Decode and validate a Supabase user access token.

    Raises ``jwt.PyJWTError`` (and subclasses) when the token is invalid.
    """
    supabase_url = settings.supabase_url.rstrip("/")
    if not supabase_url:
        raise jwt.InvalidTokenError("SUPABASE_URL is not configured")

    signing_key = _jwks_client(supabase_url).get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=list(_ALGORITHMS),
        audience=settings.supabase_jwt_audience,
        issuer=f"{supabase_url}/auth/v1",
    )

    raw_sub = payload.get("sub")
    if not raw_sub:
        raise jwt.InvalidTokenError("missing sub claim")
    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        raise jwt.InvalidTokenError("missing email claim")

    return AuthClaims(
        user_id=UUID(str(raw_sub)),
        email=email.strip(),
        display_name=_display_name_from_metadata(payload.get("user_metadata")),
    )
