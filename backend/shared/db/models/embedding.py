"""Embedding model — pgvector column(s) with FK to shoe."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

# text-embedding-3-small (shared/config.py default). If the embedding model
# changes, this dimension and the vectors must be re-indexed together.
EMBEDDING_DIM = 1536


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shoe_id: Mapped[int] = mapped_column(
        ForeignKey("shoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The normalized review/spec text chunk this vector was computed from.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Scrape source the chunk came from (provenance for source-credited explanations).
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Must match settings.embedding_model_id at query time.
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
