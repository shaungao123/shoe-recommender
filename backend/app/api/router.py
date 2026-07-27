"""Top-level API router — mount route modules here."""

from fastapi import APIRouter

from app.api.routes.recommend import router as recommend_router
from app.api.routes.shoes import router as shoes_router

api_router = APIRouter()
api_router.include_router(shoes_router)
api_router.include_router(recommend_router)


@api_router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
