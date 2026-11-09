"""Picks the top N candidates: retrieval fit plus the shopper's stated priorities.

Quiz answers are boosts, not filters, because many shoes have data gaps: a shoe
with no rating gets a below-average value rather than being excluded. Scores
are read from one source at a time and never averaged across sources. Equal
totals resolve by review score, then shoe id, so results never depend on chance.
"""

from __future__ import annotations

from app.db.repositories.shoes import SCORE_SOURCE
from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendRequest

# Similarity usually spans ~0.1-0.2 across a candidate pool, so these are sized
# to reorder close matches without letting one answer override a poor fit.
COURT_WEIGHT = 0.12
PRIORITY_WEIGHT = 0.12
WIDTH_WEIGHT = 0.08
BRAND_WEIGHT = 0.08
CUT_WEIGHT = 0.06
UNPRICED_PENALTY = 0.03
TAG_OVERLAP_WEIGHT = 0.1

UNKNOWN_VALUE = 0.4  # just under a typical rating, so known data wins ties
RATING_FLOOR = 5.0  # reviewers rarely score below this on their 0-10 scale
STRONG_RATING = 8.0
MAX_REASONS = 3
LIGHT_OZ, HEAVY_OZ = 12.0, 16.0
LIGHT_ENOUGH_OZ = 14.0

_OUTDOOR_SUITABILITY = {"good": 1.0, "fair": 0.5, "bad": 0.0}
_FOOT_WIDTH_FIT = {
    "wide": {"wide": 1.0, "standard": 0.6, "narrow": 0.0},
    "narrow": {"narrow": 1.0, "standard": 0.6, "wide": 0.2},
}
_PRIORITY_LABELS = {"traction": "traction", "cushion": "cushion", "support": "support"}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _rating(candidate: Candidate, metric: str) -> float | None:
    return _number((candidate.metrics.get(SCORE_SOURCE) or {}).get(metric))


def _outdoor_value(candidate: Candidate) -> tuple[float, str | None]:
    """How outdoor-ready a shoe is (0-1) and a reason when a reviewer measured it."""
    raw = (candidate.metrics.get(SCORE_SOURCE) or {}).get("outdoor")
    try:
        percent = int(str(raw).rstrip("%"))
    except ValueError:
        percent = None
    if percent is not None:
        return percent / 100, f"{percent}% outdoor durability" if percent >= 50 else None
    lab_score = _number((candidate.metrics.get("runrepeat") or {}).get("score_outdoor"))
    if lab_score is not None:
        return lab_score / 100, f"{lab_score:.0f}/100 outdoor score" if lab_score >= 50 else None
    suitability = (candidate.specs or {}).get("outdoor_suitability")
    # Scraped spec with mixed provenance: it can rank a shoe, but isn't quoted as a reason.
    return _OUTDOOR_SUITABILITY.get(suitability, UNKNOWN_VALUE), None


def _priority_value(candidate: Candidate, priority: str) -> tuple[float, str | None]:
    if priority == "lightweight":
        ounces = _number((candidate.specs or {}).get("weight_oz"))
        if ounces is None:
            return UNKNOWN_VALUE, None
        return _clamp((HEAVY_OZ - ounces) / (HEAVY_OZ - LIGHT_OZ)), f"{ounces:g} oz" if ounces <= LIGHT_ENOUGH_OZ else None
    rating = _rating(candidate, priority)
    if rating is None:
        return UNKNOWN_VALUE, None
    reason = f"{rating:.1f} {_PRIORITY_LABELS[priority]}" if rating >= STRONG_RATING else None
    return _clamp((rating - RATING_FLOOR) / (10 - RATING_FLOOR)), reason


def _total(candidate: Candidate, request: RecommendRequest | None) -> tuple[float, list[str]]:
    if candidate.similarity is not None:
        total = candidate.similarity
    else:
        total = (candidate.tag_overlap or 0) * TAG_OVERLAP_WEIGHT
    if candidate.price is None:
        total -= UNPRICED_PENALTY
    if request is None:
        return total, []

    reasons: list[str] = []
    for priority in request.priorities:
        value, reason = _priority_value(candidate, priority)
        total += PRIORITY_WEIGHT * value
        if reason:
            reasons.append(reason)

    if request.court in ("outdoor", "both"):
        value, reason = _outdoor_value(candidate)
        total += COURT_WEIGHT * value * (1.0 if request.court == "outdoor" else 0.5)
        if reason:
            reasons.append(reason)

    specs = candidate.specs or {}
    fits = _FOOT_WIDTH_FIT.get(request.foot_width or "")
    if fits:
        shoe_width = specs.get("width_fit")
        total += WIDTH_WEIGHT * fits.get(shoe_width, UNKNOWN_VALUE)
        if shoe_width == request.foot_width:
            reasons.append(f"{str(shoe_width).capitalize()} fit")

    if request.preferred_brand and candidate.brand.lower() == request.preferred_brand.lower():
        total += BRAND_WEIGHT
        reasons.append(candidate.brand)

    if request.preferred_cut and specs.get("cut_height") == request.preferred_cut:
        total += CUT_WEIGHT
        reasons.append(f"{request.preferred_cut.capitalize()} cut")

    return total, reasons[:MAX_REASONS]


def select_top_candidates(
    candidates: list[Candidate], n: int, request: RecommendRequest | None = None
) -> list[Candidate]:
    """Best ``n`` candidates, each annotated with why it matched the shopper."""
    if n <= 0:
        return []
    scored = [(candidate, *_total(candidate, request)) for candidate in candidates]
    scored.sort(
        key=lambda item: (-round(item[1], 4), -(_rating(item[0], "overall") or 0), item[0].shoe_id)
    )
    return [
        candidate.model_copy(update={"match_reasons": reasons})
        for candidate, _, reasons in scored[:n]
    ]
