"""Saved quiz answers and the personal shoe verdict built from them."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.recommend import Court, Cut, FootWidth, Priority, RecommendRequest

Position = Literal["guard", "wing", "big"]
Style = Literal["slasher", "shooter", "all-around", "post", "defender", "speedster"]


class Preferences(BaseModel):
    """The quiz answers, in the shape the quiz collects them."""

    model_config = ConfigDict(extra="forbid")

    positions: list[Position] = Field(default_factory=list, max_length=3)
    styles: list[Style] = Field(default_factory=list, max_length=6)
    description: str = Field("", max_length=500, description="Their game in their own words")
    court: Court | None = None
    priorities: list[Priority] = Field(default_factory=list, max_length=2)
    budget: float | None = Field(None, ge=0)
    foot_width: FootWidth | None = None
    preferred_brand: str | None = Field(None, max_length=128)
    preferred_cut: Cut | None = None
    note: str = Field("", max_length=500, description="Anything else, e.g. an injury")

    @field_validator("description", "note")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("positions", "styles", "priorities")
    @classmethod
    def _dedupe(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    def playstyle_text(self) -> str:
        """Same wording the quiz sends as ``playstyle`` (frontend buildRequest)."""
        parts = [
            ", ".join(p.capitalize() for p in self.positions),
            ", ".join(s.capitalize() for s in self.styles),
            self.description,
            self.note,
        ]
        return " — ".join(part for part in parts if part)

    def to_request(self) -> RecommendRequest:
        """The recommend request these answers would make, minus the budget.

        Verdicts judge how a shoe fits the player, so price plays no part.
        """
        return RecommendRequest.model_construct(
            playstyle=self.playstyle_text(),
            budget=None,
            aesthetic=None,
            court=self.court,
            priorities=list(self.priorities),
            foot_width=self.foot_width,
            preferred_brand=self.preferred_brand,
            preferred_cut=self.preferred_cut,
            brand=None,
            outdoor=None,
            cut=None,
            width=None,
            position=None,
            playstyle_tag=None,
        )


class PreferencesResponse(Preferences):
    updated_at: datetime


VerdictLevel = Literal["great", "worth_a_look", "not_for_you"]


class Verdict(BaseModel):
    level: VerdictLevel
    label: str
    reasons: list[str] = Field(default_factory=list, description="Ways the shoe matches")
    caveats: list[str] = Field(default_factory=list, description="Ways it works against them")
    unknowns: list[str] = Field(default_factory=list, description="Priorities with no data")


class VerdictResponse(BaseModel):
    """``verdict`` is null when the user has no saved preferences yet."""

    has_preferences: bool
    verdict: Verdict | None = None
