"""FastAPI dependency injection (DB sessions, services)."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db

GetDbDep = Generator[Session, None, None]


def get_db() -> GetDbDep:
    yield from _get_db()
