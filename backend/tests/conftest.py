"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.db import models  # noqa: F401 — register model metadata
from shared.db.base import Base


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """In-memory SQLite session with all tables created.

    Fine for repository/retriever logic that doesn't touch pgvector operators;
    anything exercising cosine_distance needs real Postgres and isn't unit-tested.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
