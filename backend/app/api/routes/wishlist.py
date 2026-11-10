"""Wishlist routes for the authenticated user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.shoes import _summary_from_row
from app.db.repositories import shoes as shoes_repo
from app.db.repositories import wishlist as wishlist_repo
from app.db.session import get_db
from app.dependencies import get_current_user
from app.schemas.wishlist import WishlistItemResponse, WishlistResponse
from shared.db.models import User

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=WishlistResponse)
def get_wishlist(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WishlistResponse:
    rows = wishlist_repo.list_items(db, user.id)
    return WishlistResponse(
        items=[
            WishlistItemResponse(
                shoe=_summary_from_row(shoe),
                saved_at=item.created_at,
            )
            for item, shoe in rows
        ]
    )


@router.put("/{shoe_id}", response_model=WishlistItemResponse, status_code=status.HTTP_200_OK)
def put_wishlist_item(
    shoe_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WishlistItemResponse:
    shoe = shoes_repo.get_shoe(db, shoe_id)
    if shoe is None:
        raise HTTPException(status_code=404, detail="Shoe not found")
    item = wishlist_repo.add_item(db, user.id, shoe_id)
    return WishlistItemResponse(shoe=_summary_from_row(shoe), saved_at=item.created_at)


@router.delete("/{shoe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wishlist_item(
    shoe_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    wishlist_repo.remove_item(db, user.id, shoe_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
