"""Pydantic schemas shaped to the live ``shoes`` table / pipeline upsert.

Column + JSON keys match what ``pipeline.upsert.writer`` writes into Supabase
(pilot corpus: 30 shoes). ``affiliate_url`` is always null today.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ShoeSpecs(BaseModel):
    """``shoes.specs`` JSON — keys from pipeline SPEC_FIELDS."""

    version: str | None = None
    release_year: int | None = None
    signature_player: str | None = None
    weight_oz: float | None = None
    weight_g: float | None = None
    drop_mm: float | None = None
    stack_heel_mm: float | None = None
    stack_forefoot_mm: float | None = None
    cut_height: str | None = None  # low | mid | high
    width_fit: str | None = None  # narrow | standard | wide
    length_fit: str | None = None
    cushioning_tech: str | None = None
    traction_pattern: str | None = None
    outdoor_suitability: str | None = None  # good | fair | bad
    position_tags: list[str] = Field(default_factory=list)  # guard | wing | big
    playstyle_tags: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    source: str
    url: str
    fetched_at: str | None = None


class TextSnippet(BaseModel):
    source: str
    text: str


class ShoeExtraMetadata(BaseModel):
    """``shoes.extra_metadata`` JSON — keys from pipeline METADATA_FIELDS."""

    metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    pros: list[TextSnippet] = Field(default_factory=list)
    cons: list[TextSnippet] = Field(default_factory=list)
    review_text: list[TextSnippet] = Field(default_factory=list)
    provenance: dict[str, dict[str, str]] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)


class ShoeSummary(BaseModel):
    """Browse card — columns + well-filled spec fields from the corpus."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_id: str | None = None
    brand: str
    name: str
    price: float
    currency: str
    image_url: str | None = None
    affiliate_url: str | None = None
    # Specs lifted for cards (fill rates on current pilot: cut/outdoor/width/weight ~100%)
    release_year: int | None = None
    signature_player: str | None = None
    weight_oz: float | None = None
    cut_height: str | None = None
    width_fit: str | None = None
    outdoor_suitability: str | None = None
    cushioning_tech: str | None = None
    position_tags: list[str] = Field(default_factory=list)
    playstyle_tags: list[str] = Field(default_factory=list)


class ShoeDetail(ShoeSummary):
    source_url: str | None = None
    specs: ShoeSpecs = Field(default_factory=ShoeSpecs)
    extra_metadata: ShoeExtraMetadata = Field(default_factory=ShoeExtraMetadata)
    created_at: datetime
    updated_at: datetime


class ShoeListResponse(BaseModel):
    items: list[ShoeSummary]
    total: int
    limit: int
    offset: int
