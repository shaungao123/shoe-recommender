""""Would you like it?": where one shoe ranks for a user's saved quiz answers.

Every shoe in the catalog is scored the way the recommender scores its pool
(best-chunk similarity plus the quiz boosts in ``ranking``), with price left
out, and the shoe's rank decides the verdict: top 5% is a great fit, top 30%
is worth a look. Reasons, caveats and unknowns come from the same answers.
"""

from __future__ import annotations

import logging
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.repositories import preferences as preferences_repo
from app.db.repositories.shoes import best_similarity_by_shoe
from app.schemas.candidate import Candidate
from app.schemas.preferences import Preferences, Verdict, VerdictResponse
from app.services import ranking
from app.services.rag.embedder import embed_query
from app.services.rag.retriever import build_query_text
from app.services.recommend import _shopper_profile
from shared.config import settings
from shared.db.models import Shoe, User, UserPreferences
from shared.embedding import EmbeddingClient, EmbeddingError
from shared.tags import extract_tags

logger = logging.getLogger(__name__)

GREAT_SHARE = 0.05
WORTH_SHARE = 0.30
MAX_REASONS, MAX_CAVEATS, MAX_UNKNOWNS = 3, 2, 2
WEAK_RATING = 7.0  # reviewers' 0-10 scale; below this a priority counts against the shoe
WEAK_OUTDOOR = 0.5
HEAVY_OZ = 14.0

LABELS = {
    "great": "Great fit for you",
    "worth_a_look": "Worth a look",
    "not_for_you": "Probably not for you",
}
_PLURAL = {"guard": "guards", "wing": "wings", "big": "bigs"}
_STYLE_NOUN = {
    "slasher": "slashers",
    "shooter": "shooters",
    "post": "post players",
    "defender": "defenders",
    "speedster": "quick players",
}
_PRIORITY_NOUN = {
    "traction": "traction",
    "cushion": "cushion",
    "support": "support",
    "lightweight": "weight",
}


def profile_text(preferences: Preferences) -> str:
    """The text embedded for this profile: the recommender's query for these answers."""
    shopper = _shopper_profile(preferences.to_request())
    return build_query_text(shopper, "") if shopper else ""


def refresh_profile_vector(
    session: Session, row: UserPreferences, client: EmbeddingClient | None = None
) -> list[float] | None:
    """The stored profile vector, re-embedding only when the answers' text changed."""
    text = profile_text(Preferences(**row.answers))
    model_id = client.model_id if client else settings.embedding_model_id
    if not text:
        return None
    if row.profile_vector is not None and row.profile_text == text and row.profile_model_id == model_id:
        return list(row.profile_vector)
    try:
        vector = embed_query(text, client=client)
    except EmbeddingError as exc:
        logger.warning("profile embedding failed; using tag overlap: %s", exc)
        return None
    preferences_repo.store_profile_vector(session, row, text, model_id, vector)
    return vector


def _catalog_candidates(
    session: Session, preferences: Preferences, vector: list[float] | None, model_id: str
) -> list[Candidate]:
    # Only what scoring reads: review text makes up most of each row and isn't needed.
    rows = session.execute(
        select(Shoe.id, Shoe.brand, Shoe.name, Shoe.price, Shoe.specs, Shoe.extra_metadata["metrics"])
    ).all()
    candidates = [
        Candidate(
            shoe_id=shoe_id,
            brand=brand,
            name=name,
            price=float(price) if price is not None else None,
            specs=specs or {},
            metrics=metrics or {},
        )
        for shoe_id, brand, name, price, specs, metrics in rows
    ]
    if vector is None:
        # Same fallback as the recommender: tag overlap with the player's own words.
        wanted = extract_tags(preferences.playstyle_text())
        for candidate in candidates:
            tags = set(candidate.specs.get("playstyle_tags") or []) | set(candidate.specs.get("position_tags") or [])
            candidate.tag_overlap = len(tags & wanted)
        return candidates
    similarity = best_similarity_by_shoe(session, vector, model_id)
    floor = min(similarity.values(), default=0.0)  # shoes without embeddings rank as the weakest match
    for candidate in candidates:
        candidate.similarity = similarity.get(candidate.shoe_id, floor)
    return candidates


def level_for_rank(index: int, total: int) -> str:
    """Verdict level for a 0-based rank among ``total`` shoes."""
    if index < math.ceil(total * GREAT_SHARE):
        return "great"
    if index < math.ceil(total * WORTH_SHARE):
        return "worth_a_look"
    return "not_for_you"


def fit_notes(candidate: Candidate, preferences: Preferences) -> tuple[list[str], list[str], list[str]]:
    """(reasons, caveats, unknowns) for one shoe against the saved answers."""
    reasons: list[str] = []
    caveats: list[str] = []
    unknowns: list[str] = []
    specs = candidate.specs or {}

    for index, priority in enumerate(preferences.priorities):
        noun = _PRIORITY_NOUN[priority]
        why = "your top priority" if index == 0 else "one of your priorities"
        if priority == "lightweight":
            ounces = ranking._number(specs.get("weight_oz"))
            if ounces is None:
                unknowns.append("No weight listed")
            elif ounces <= ranking.LIGHT_ENOUGH_OZ:
                reasons.append(f"{ounces:g} oz — light, like you wanted")
            elif ounces > HEAVY_OZ:
                caveats.append(f"Heavier than you asked for ({ounces:g} oz)")
            continue
        rating = ranking._rating(candidate, priority)
        if rating is None:
            unknowns.append(f"No {noun} rating yet")
        elif rating >= ranking.STRONG_RATING:
            reasons.append(f"{rating:.1f} {noun} — {why}")
        elif rating < WEAK_RATING:
            caveats.append(f"Only {rating:.1f} {noun}, and you want strong {noun}")

    shoe_positions = set(specs.get("position_tags") or [])
    wanted_positions = set(preferences.positions)
    if wanted_positions and shoe_positions:
        matched = [p for p in preferences.positions if p in shoe_positions]
        if matched:
            reasons.append(f"Built for {_PLURAL[matched[0]]}")
        elif built_for := " and ".join(_PLURAL[p] for p in ("guard", "wing", "big") if p in shoe_positions):
            caveats.append(f"Built more for {built_for}")
    if "leaper" in preferences.styles and "bouncy" in (specs.get("trait_tags") or []):
        reasons.append("Bouncy cushioning, per reviewers")
    styles = [s for s in preferences.styles if s in set(specs.get("playstyle_tags") or [])]
    if styles and styles[0] in _STYLE_NOUN:
        reasons.append(f"Suits {_STYLE_NOUN[styles[0]]}")

    if preferences.court in ("outdoor", "both"):
        value, reason = ranking._outdoor_value(candidate)
        has_outdoor_data = (
            (candidate.metrics.get(ranking.SCORE_SOURCE) or {}).get("outdoor") is not None
            or (candidate.metrics.get("runrepeat") or {}).get("score_outdoor") is not None
            or specs.get("outdoor_suitability") in ranking._OUTDOOR_SUITABILITY
        )
        if reason:
            reasons.append(reason)
        elif not has_outdoor_data:
            unknowns.append("No outdoor durability data")
        elif preferences.court == "outdoor" and value < WEAK_OUTDOOR:
            caveats.append("Not built for rough outdoor courts")

    width = specs.get("width_fit")
    if preferences.foot_width:
        if width == preferences.foot_width:
            reasons.append(f"{width.capitalize()} fit matches your feet")
        elif width is None and preferences.foot_width != "standard":
            unknowns.append("Width fit not reported")
        elif preferences.foot_width == "wide" and width == "narrow":
            caveats.append("Runs narrow for wide feet")
        elif preferences.foot_width == "narrow" and width == "wide":
            caveats.append("Roomy for narrow feet")

    cut = specs.get("cut_height")
    if preferences.preferred_cut and cut:
        if cut == preferences.preferred_cut:
            reasons.append(f"{cut.capitalize()} cut, as you prefer")
        else:
            caveats.append(f"{cut.capitalize()} cut — you prefer {preferences.preferred_cut}")

    if preferences.preferred_brand and candidate.brand.lower() == preferences.preferred_brand.lower():
        reasons.append(f"{candidate.brand} — your preferred brand")

    return reasons[:MAX_REASONS], caveats[:MAX_CAVEATS], unknowns[:MAX_UNKNOWNS]


def verdict_for(
    session: Session, user: User, shoe: Shoe, client: EmbeddingClient | None = None
) -> VerdictResponse:
    row = preferences_repo.get_preferences(session, user.id)
    if row is None:
        return VerdictResponse(has_preferences=False)
    preferences = Preferences(**row.answers)
    request = preferences.to_request()
    model_id = client.model_id if client else settings.embedding_model_id
    vector = refresh_profile_vector(session, row, client)

    candidates = _catalog_candidates(session, preferences, vector, model_id)
    ranked = sorted(
        candidates,
        key=lambda c: ranking.rank_key(c, ranking._total(c, request, ignore_price=True)[0]),
    )
    index = next(i for i, c in enumerate(ranked) if c.shoe_id == shoe.id)
    level = level_for_rank(index, len(ranked))
    reasons, caveats, unknowns = fit_notes(ranked[index], preferences)
    return VerdictResponse(
        has_preferences=True,
        verdict=Verdict(
            level=level, label=LABELS[level], reasons=reasons, caveats=caveats, unknowns=unknowns
        ),
    )
