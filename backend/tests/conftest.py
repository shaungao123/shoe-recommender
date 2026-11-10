"""Shared pytest fixtures — in-memory SQLite, no network.

``seed_shoe`` defaults mirror a real Supabase pilot row (pipeline upsert shape).
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.dependencies import get_current_user
from app.main import create_app
from shared.db import models  # noqa: F401 — register model metadata
from shared.db.base import Base
from shared.db.models import Shoe, User

_DEFAULT_SPECS = {
    "version": "3",
    "release_year": 2024,
    "signature_player": None,
    "weight_oz": 12.5,
    "weight_g": 354.4,
    "drop_mm": 8.0,
    "stack_heel_mm": 24.0,
    "stack_forefoot_mm": 18.0,
    "cut_height": "low",
    "width_fit": "standard",
    "length_fit": "true_to_size",
    "cushioning_tech": "ZoomX",
    "traction_pattern": "Herringbone",
    "outdoor_suitability": "fair",
    "position_tags": ["guard"],
    "playstyle_tags": ["slasher", "shooter"],
}

_DEFAULT_METADATA = {
    "metrics": {
        "runrepeat": {"corescore": 90, "score_cushioning": 85},
        "thehoopsgeek": {"overall": 8.5, "traction": 8.8},
    },
    "pros": [{"source": "runrepeat", "text": "elite grip"}],
    "cons": [{"source": "runrepeat", "text": "pricey"}],
    "review_text": [
        {"source": "runrepeat", "text": "[our verdict] Great court feel."}
    ],
    "provenance": {
        "msrp_usd_cents": {
            "source": "runrepeat",
            "url": "https://runrepeat.com/nike-gt-cut-3",
            "fetched_at": "2026-07-04T00:00:00+00:00",
        }
    },
    "sources": [
        {
            "source": "basketballshoespecs",
            "url": "https://www.basketballshoespecs.com/shoes/nike-gt-cut-3/",
            "fetched_at": "2026-07-04T00:00:00+00:00",
        }
    ],
}


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """In-memory SQLite session with all tables created.

    Fine for repository/retriever/API logic that doesn't touch pgvector operators;
    anything exercising cosine_distance needs real Postgres and isn't unit-tested.
    StaticPool so the TestClient and seed helpers share one connection.
    Foreign keys are on so wishlist cascades can be asserted.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(text("PRAGMA foreign_keys=ON"))
        yield session


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_user(
    session: Session,
    *,
    user_id: UUID | None = None,
    email: str = "player@example.com",
    display_name: str | None = "Player One",
) -> User:
    row = User(
        id=user_id or uuid4(),
        email=email,
        display_name=display_name,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@pytest.fixture()
def auth_user(db_session: Session) -> User:
    return seed_user(db_session)


@pytest.fixture()
def auth_client(client: TestClient, auth_user: User) -> Generator[TestClient, None, None]:
    """TestClient with get_current_user overridden to a seeded profile."""
    app = client.app

    def override_user() -> User:
        return auth_user

    app.dependency_overrides[get_current_user] = override_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def seed_shoe(session: Session, **kwargs) -> Shoe:
    """Insert a shoe shaped like the live corpus (e.g. jordan-40 / dame-9)."""
    specs_override = kwargs.pop("specs", None)
    meta_override = kwargs.pop("extra_metadata", None)
    defaults = dict(
        canonical_id="nike-gt-cut-3",
        brand="Nike",
        name="G.T. Cut 3",
        price=Decimal("190.00"),
        currency="USD",
        image_url="https://example.com/gt3.jpg",
        affiliate_url=None,
        source_url="https://www.basketballshoespecs.com/shoes/nike-gt-cut-3/",
        specs={**_DEFAULT_SPECS, **(specs_override or {})},
        extra_metadata={**_DEFAULT_METADATA, **(meta_override or {})},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    row = Shoe(**defaults)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
