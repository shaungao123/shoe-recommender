"""Shoe queries: list with hard filters, get by id.

Filters map to real columns / ``specs`` keys present in the Supabase corpus.
"""

from __future__ import annotations

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from shared.db.models import Shoe


def _json_str(shoe_col, key: str):
    """Scalar JSON field as text — works on SQLite and Postgres."""
    return shoe_col[key].as_string()


def _json_array_contains(shoe_col, key: str, value: str):
    """True when a JSON string-array field contains ``value``.

    Portable across SQLite (tests) and Postgres: match the quoted token in
    the serialized array. Fine for a small shoe corpus.
    """
    return cast(shoe_col[key], String).like(f'%"{value}"%')


def _apply_filters(
    stmt,
    *,
    brand: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    outdoor: str | None = None,
    playstyle: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
):
    if brand is not None:
        stmt = stmt.where(func.lower(Shoe.brand) == brand.lower())
    if budget_min is not None:
        stmt = stmt.where(Shoe.price >= budget_min)
    if budget_max is not None:
        stmt = stmt.where(Shoe.price <= budget_max)
    if outdoor is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "outdoor_suitability") == outdoor)
    if cut is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "cut_height") == cut)
    if width is not None:
        stmt = stmt.where(_json_str(Shoe.specs, "width_fit") == width)
    if playstyle is not None:
        stmt = stmt.where(_json_array_contains(Shoe.specs, "playstyle_tags", playstyle))
    if position is not None:
        stmt = stmt.where(_json_array_contains(Shoe.specs, "position_tags", position))
    return stmt


def list_shoes(
    session: Session,
    *,
    brand: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    outdoor: str | None = None,
    playstyle: str | None = None,
    cut: str | None = None,
    width: str | None = None,
    position: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Shoe], int]:
    """Return matching shoes (price asc, then name) and total match count."""
    filters = dict(
        brand=brand,
        budget_min=budget_min,
        budget_max=budget_max,
        outdoor=outdoor,
        playstyle=playstyle,
        cut=cut,
        width=width,
        position=position,
    )
    base = _apply_filters(select(Shoe), **filters)
    total = session.scalar(
        _apply_filters(select(func.count()).select_from(Shoe), **filters)
    ) or 0
    rows = list(
        session.scalars(
            base.order_by(Shoe.price.asc(), Shoe.name.asc()).limit(limit).offset(offset)
        )
    )
    return rows, total


def get_shoe(session: Session, shoe_id: int) -> Shoe | None:
    return session.get(Shoe, shoe_id)
