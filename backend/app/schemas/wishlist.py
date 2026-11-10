"""Wishlist request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.shoes import ShoeSummary


class WishlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shoe: ShoeSummary
    saved_at: datetime


class WishlistResponse(BaseModel):
    items: list[WishlistItemResponse]
