"""Top-level API router — mount route modules here."""

from fastapi import APIRouter

from app.api.routes.recommend import router as recommend_router
from app.api.routes.shoes import router as shoes_router

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

api_router = APIRouter()
api_router.include_router(shoes_router)
api_router.include_router(recommend_router)


@api_router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@api_router.get("/health/ready")
def readiness_check(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
