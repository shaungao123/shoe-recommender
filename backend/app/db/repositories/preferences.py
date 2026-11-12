"""Saved quiz answers per user."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.preferences import Preferences
from shared.db.models import UserPreferences


def get_preferences(session: Session, user_id: UUID) -> UserPreferences | None:
    return session.get(UserPreferences, user_id)


def save_preferences(session: Session, user_id: UUID, preferences: Preferences) -> UserPreferences:
    """Replace the user's answers.

    The profile vector stays until the verdict service sees its text no longer
    matches the answers and re-embeds.
    """
    row = session.get(UserPreferences, user_id)
    answers = preferences.model_dump(mode="json")
    if row is None:
        row = UserPreferences(user_id=user_id, answers=answers)
        session.add(row)
    else:
        row.answers = answers
    session.commit()
    session.refresh(row)
    return row


def store_profile_vector(
    session: Session, row: UserPreferences, text: str, model_id: str, vector: list[float]
) -> None:
    row.profile_text, row.profile_model_id, row.profile_vector = text, model_id, vector
    session.commit()
