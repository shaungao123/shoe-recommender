"""GET /shoes — browse with hard filters; GET /shoes/{id} — detail.

Response shapes mirror the live ``shoes`` rows produced by the pipeline upsert.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.repositories import shoes as shoes_repo
from app.db.session import get_db
from app.schemas.shoes import (
    ShoeDetail,
    ShoeExtraMetadata,
    ShoeListResponse,
    ShoeSpecs,
    ShoeSummary,
)
from shared.db.models import Shoe

router = APIRouter(prefix="/shoes", tags=["shoes"])


def _summary_from_row(row: Shoe) -> ShoeSummary:
    specs: dict[str, Any] = row.specs or {}
    return ShoeSummary(
        id=row.id,
        canonical_id=row.canonical_id,
        brand=row.brand,
        name=row.name,
        price=float(row.price),
        currency=row.currency,
        image_url=row.image_url,
        affiliate_url=row.affiliate_url,
        release_year=specs.get("release_year"),
        signature_player=specs.get("signature_player"),
        weight_oz=specs.get("weight_oz"),
        cut_height=specs.get("cut_height"),
        width_fit=specs.get("width_fit"),
        outdoor_suitability=specs.get("outdoor_suitability"),
        cushioning_tech=specs.get("cushioning_tech"),
        position_tags=list(specs.get("position_tags") or []),
        playstyle_tags=list(specs.get("playstyle_tags") or []),
    )


def _detail_from_row(row: Shoe) -> ShoeDetail:
    base = _summary_from_row(row)
    return ShoeDetail(
        **base.model_dump(),
        source_url=row.source_url,
        specs=ShoeSpecs.model_validate(row.specs or {}),
        extra_metadata=ShoeExtraMetadata.model_validate(row.extra_metadata or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=ShoeListResponse)
def list_shoes(
    db: Annotated[Session, Depends(get_db)],
    brand: str | None = Query(
        None, description="Exact brand match, case-insensitive (e.g. Nike, Jordan)"
    ),
    budget_min: float | None = Query(None, ge=0),
    budget_max: float | None = Query(None, ge=0),
    outdoor: str | None = Query(
        None, description="specs.outdoor_suitability: good | fair | bad"
    ),
    playstyle: str | None = Query(
        None, description="Must appear in specs.playstyle_tags (e.g. slasher)"
    ),
    cut: str | None = Query(None, description="specs.cut_height: low | mid | high"),
    width: str | None = Query(
        None, description="specs.width_fit: narrow | standard | wide"
    ),
    position: str | None = Query(
        None, description="Must appear in specs.position_tags: guard | wing | big"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ShoeListResponse:
    if (
        budget_min is not None
        and budget_max is not None
        and budget_min > budget_max
    ):
        raise HTTPException(
            status_code=422,
            detail="budget_min must be less than or equal to budget_max",
        )
    rows, total = shoes_repo.list_shoes(
        db,
        brand=brand,
        budget_min=budget_min,
        budget_max=budget_max,
        outdoor=outdoor,
        playstyle=playstyle,
        cut=cut,
        width=width,
        position=position,
        limit=limit,
        offset=offset,
    )
    return ShoeListResponse(
        items=[_summary_from_row(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{shoe_id}", response_model=ShoeDetail)
def get_shoe(
    shoe_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ShoeDetail:
    row = shoes_repo.get_shoe(db, shoe_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Shoe not found")
    return _detail_from_row(row)
