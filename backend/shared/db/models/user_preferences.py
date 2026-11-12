"""A signed-in user's saved quiz answers, plus the embedded profile used to match shoes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from shared.db.base import Base
from shared.db.models.embedding import EMBEDDING_DIM


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Quiz answers, validated by app.schemas.preferences.Preferences.
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # The text that was embedded and the model it was embedded with; the vector
    # is refreshed whenever the text changes, so page views never call the API.
    profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    profile_vector: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
