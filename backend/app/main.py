"""FastAPI application entrypoint — app factory to be implemented."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from shared.config import settings
from shared.db.models import Shoe  # noqa: F401 — register model metadata


def create_app() -> FastAPI:
    app = FastAPI(title="Shoe Recommender API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
