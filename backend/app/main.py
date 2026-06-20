"""FastAPI application entrypoint — app factory to be implemented."""

from fastapi import FastAPI

from app.api.router import api_router
from shared.db.models import Shoe  # noqa: F401 — register model metadata


def create_app() -> FastAPI:
    app = FastAPI(title="Shoe Recommender API")
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
