"""Pydantic schemas for recommendation request and response."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Court = Literal["indoor", "outdoor", "both"]
Priority = Literal["traction", "cushion", "support", "lightweight"]
FootWidth = Literal["narrow", "standard", "wide"]
Cut = Literal["low", "mid", "high"]


class EvidenceSnippet(BaseModel):
    source: str | None = None
    text: str


class RecommendRequest(BaseModel):
    """Frontend intake + optional browse-style hard filters."""

    playstyle: str | None = Field(None, description="Natural-language playstyle")
    budget: float | None = Field(
        None, ge=0, description="Max price; null means no cap ($180+)"
    )
    aesthetic: str | None = Field(None, description="Optional style / look free text")
    # Quiz answers. These reorder results; only budget and the filters below exclude shoes.
    court: Court | None = None
    priorities: list[Priority] = Field(default_factory=list, max_length=2)
    foot_width: FootWidth | None = None
    preferred_brand: str | None = Field(default=None, max_length=128)
    preferred_cut: Cut | None = None
    brand: str | None = None
    outdoor: str | None = Field(
        None, description="specs.outdoor_suitability: good | fair | bad"
    )
    cut: str | None = Field(None, description="specs.cut_height: low | mid | high")
    width: str | None = Field(
        None, description="specs.width_fit: narrow | standard | wide"
    )
    position: str | None = Field(
        None, description="Must appear in specs.position_tags: guard | wing | big"
    )
    playstyle_tag: str | None = Field(
        None,
        description="Exact tag in specs.playstyle_tags (hard filter, not NL playstyle)",
    )

    @model_validator(mode="after")
    def at_least_one_criterion(self) -> "RecommendRequest":
        if self.budget is not None:
            return self
        if (self.playstyle or "").strip():
            return self
        if (self.aesthetic or "").strip():
            return self
        if any(
            (
                self.court,
                self.priorities,
                self.foot_width,
                self.preferred_brand,
                self.preferred_cut,
                self.brand,
                self.outdoor,
                self.cut,
                self.width,
                self.position,
                self.playstyle_tag,
            )
        ):
            return self
        raise ValueError("At least one search criterion is required")


class RecommendedShoe(BaseModel):
    """One recommendation card — aligned with frontend RecommendedShoe."""

    id: int
    brand: str
    model: str
    price: float | None
    image_url: str | None = None
    affiliate_url: str | None = None
    specs: list[str] = Field(default_factory=list)
    explanation: str
    evidence: list[EvidenceSnippet] = Field(default_factory=list)
    similarity: float | None = None
    match_reasons: list[str] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    recommendations: list[RecommendedShoe]
