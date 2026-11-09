"""Pydantic schemas for recommendation request and response."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AestheticPreferences(BaseModel):
    """Soft visual preferences; corpus gaps must never turn these into exclusions."""

    preferred_brand: str | None = Field(default=None, max_length=128)
    color_family: Literal["neutral", "dark", "bright", "team"] | None = None
    visual_direction: Literal["classic_retro", "modern_technical", "minimal"] | None = None
    silhouette: Literal["low", "mid", "high"] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_ui_field_names(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "preferred_brand" not in normalized and "brand" in normalized:
            normalized["preferred_brand"] = normalized["brand"]
        if normalized.get("color_family") == "team_colors":
            normalized["color_family"] = "team"
        return normalized

    def query_terms(self) -> str:
        labels = {
            "classic_retro": "classic retro",
            "modern_technical": "modern technical",
        }
        values = [
            self.preferred_brand,
            self.color_family,
            labels.get(self.visual_direction or "", self.visual_direction),
            self.silhouette and f"{self.silhouette} cut",
        ]
        return " ".join(str(value) for value in values if value)


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
    aesthetic_preferences: AestheticPreferences | None = None
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
        if (self.aesthetic or "").strip() or self.aesthetic_preferences is not None:
            return self
        if any(
            (
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


class RecommendResponse(BaseModel):
    recommendations: list[RecommendedShoe]
