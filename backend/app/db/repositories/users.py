"""User profile persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from shared.db.models import User


def get_user(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def upsert_from_claims(
    session: Session,
    *,
    user_id: UUID,
    email: str,
    display_name: str | None,
) -> User:
    """Create the profile on first auth request; refresh email only afterward.

    ``display_name`` from the token is copied once so later renames via PATCH
    are not overwritten by a token refresh.
    """
    row = session.get(User, user_id)
    if row is None:
        row = User(id=user_id, email=email, display_name=display_name)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    if row.email != email:
        row.email = email
        session.commit()
        session.refresh(row)
    return row


def update_display_name(session: Session, user: User, display_name: str | None) -> User:
    user.display_name = display_name
    session.commit()
    session.refresh(user)
    return user
