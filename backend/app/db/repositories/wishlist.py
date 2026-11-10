"""Wishlist persistence queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import Shoe, WishlistItem


def list_items(session: Session, user_id: UUID) -> list[tuple[WishlistItem, Shoe]]:
    stmt = (
        select(WishlistItem, Shoe)
        .join(Shoe, Shoe.id == WishlistItem.shoe_id)
        .where(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.created_at.desc(), WishlistItem.id.desc())
    )
    return list(session.execute(stmt).all())


def get_item(session: Session, user_id: UUID, shoe_id: int) -> WishlistItem | None:
    stmt = select(WishlistItem).where(
        WishlistItem.user_id == user_id,
        WishlistItem.shoe_id == shoe_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def add_item(session: Session, user_id: UUID, shoe_id: int) -> WishlistItem:
    existing = get_item(session, user_id, shoe_id)
    if existing is not None:
        return existing
    row = WishlistItem(user_id=user_id, shoe_id=shoe_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove_item(session: Session, user_id: UUID, shoe_id: int) -> None:
    row = get_item(session, user_id, shoe_id)
    if row is None:
        return
    session.delete(row)
    session.commit()
