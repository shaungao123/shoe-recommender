"""Record shapes shared by all pipeline stages.

Two shapes flow through the pipeline:

* ``SourceRecord`` — one shoe as seen by one source, already normalized to
  common units/enums but not yet merged across sources.
* ``CanonicalShoe`` — one shoe after entity resolution, with per-field
  provenance.

Everything is a plain dataclass serialized to JSON in the staging store;
nothing here touches the production DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Fixed vocabularies (enums kept as string constants so JSON stays readable)
# ---------------------------------------------------------------------------

CUT_HEIGHTS = ("low", "mid", "high")

WIDTH_FITS = ("narrow", "standard", "wide")

LENGTH_FITS = (
    "runs_small",
    "slightly_small",
    "true_to_size",
    "slightly_large",
    "runs_large",
)

OUTDOOR_SUITABILITY = ("good", "fair", "bad")

POSITION_TAGS = ("guard", "wing", "big")

PLAYSTYLE_TAGS = (
    "slasher",
    "shooter",
    "all-around",
    "post",
    "defender",
    "speedster",
)


@dataclass
class Provenance:
    """Where a field's value came from."""

    source: str
    url: str
    fetched_at: str  # ISO-8601


@dataclass
class SourceRecord:
    """One shoe as extracted from one source, in common units."""

    source: str
    url: str
    fetched_at: str
    model_raw: str  # name exactly as the source displays it

    brand: str | None = None
    model: str | None = None  # cleaned model name (brand stripped)
    version: str | None = None
    release_year: int | None = None
    signature_player: str | None = None
    msrp_usd_cents: int | None = None
    weight_oz: float | None = None
    weight_g: float | None = None
    drop_mm: float | None = None
    stack_heel_mm: float | None = None
    stack_forefoot_mm: float | None = None
    cut_height: str | None = None  # CUT_HEIGHTS
    width_fit: str | None = None  # WIDTH_FITS
    length_fit: str | None = None  # LENGTH_FITS
    cushioning_tech: str | None = None
    traction_pattern: str | None = None
    outdoor_suitability: str | None = None  # OUTDOOR_SUITABILITY
    position_tags: list[str] = field(default_factory=list)
    playstyle_tags: list[str] = field(default_factory=list)

    # Per-source scores / lab data, kept under the source's own metric names.
    scores: dict[str, Any] = field(default_factory=dict)

    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    review_text: list[str] = field(default_factory=list)  # prose segments
    image_urls: list[str] = field(default_factory=list)

    # Anything source-specific that has no canonical slot (e.g. price band).
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Fields merged one-value-per-shoe during entity resolution (everything except
# per-source containers like scores/pros/cons/review_text).
MERGEABLE_FIELDS = (
    "release_year",
    "signature_player",
    "msrp_usd_cents",
    "weight_oz",
    "weight_g",
    "drop_mm",
    "stack_heel_mm",
    "stack_forefoot_mm",
    "cut_height",
    "width_fit",
    "length_fit",
    "cushioning_tech",
    "traction_pattern",
    "outdoor_suitability",
)


@dataclass
class CanonicalShoe:
    """One shoe merged across sources, with per-field provenance."""

    canonical_id: str  # slug: brand-model-version
    brand: str
    model: str
    version: str | None = None
    release_year: int | None = None
    signature_player: str | None = None
    msrp_usd_cents: int | None = None
    weight_oz: float | None = None
    weight_g: float | None = None
    drop_mm: float | None = None
    stack_heel_mm: float | None = None
    stack_forefoot_mm: float | None = None
    cut_height: str | None = None
    width_fit: str | None = None
    length_fit: str | None = None
    cushioning_tech: str | None = None
    traction_pattern: str | None = None
    outdoor_suitability: str | None = None
    position_tags: list[str] = field(default_factory=list)
    playstyle_tags: list[str] = field(default_factory=list)

    # metrics[source] = that source's scores/lab data, never averaged.
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)

    # pros/cons/review_text keep their origin: [{"source": ..., "text": ...}]
    pros: list[dict[str, str]] = field(default_factory=list)
    cons: list[dict[str, str]] = field(default_factory=list)
    review_text: list[dict[str, str]] = field(default_factory=list)

    image_urls: list[str] = field(default_factory=list)
    affiliate_url: str | None = None  # populated by a later feed step

    # provenance[field_name] = Provenance of the winning value
    provenance: dict[str, dict[str, str]] = field(default_factory=dict)
    # every (source, url, fetched_at) that contributed to this shoe
    sources: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
