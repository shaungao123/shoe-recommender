"""Deterministic grounded explanations for retrieved candidates.

Takes the ranked Candidate list only — never queries the DB. Picks the top 3
and builds short prose from specs + best-matching snippets so the recommend
endpoint works without an LLM. Swap in structured LLM JSON later behind the
same ``explain`` signature.
"""

from __future__ import annotations

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendedShoe

TOP_N = 3

_SPEC_CHIP_KEYS = (
    ("cut_height", "{} cut"),
    ("cushioning_tech", "{}"),
    ("outdoor_suitability", "outdoor: {}"),
    ("width_fit", "{} fit"),
)


def explain(candidates: list[Candidate], *, playstyle: str = "") -> list[RecommendedShoe]:
    """Build recommendation cards for pre-selected candidates (typically ≤3)."""
    return [_to_recommendation(c, playstyle=playstyle) for c in candidates]


def _to_recommendation(candidate: Candidate, *, playstyle: str) -> RecommendedShoe:
    return RecommendedShoe(
        id=candidate.shoe_id,
        brand=candidate.brand,
        model=candidate.name,
        price=candidate.price,
        image_url=candidate.image_url,
        affiliate_url=candidate.affiliate_url,
        specs=_spec_chips(candidate),
        explanation=_build_explanation(candidate, playstyle=playstyle),
        similarity=candidate.similarity,
    )


def _spec_chips(candidate: Candidate) -> list[str]:
    specs = candidate.specs or {}
    chips: list[str] = []
    for tag in specs.get("playstyle_tags") or []:
        chips.append(str(tag).replace("_", " "))
    for tag in specs.get("position_tags") or []:
        chips.append(str(tag).replace("_", " "))
    for key, template in _SPEC_CHIP_KEYS:
        value = specs.get(key)
        if value:
            chips.append(template.format(str(value).replace("_", " ")))
    # Keep the card readable
    return chips[:6]


def _build_explanation(candidate: Candidate, *, playstyle: str) -> str:
    parts: list[str] = []
    if playstyle.strip():
        parts.append(
            f"The {candidate.brand} {candidate.name} fits a {playstyle.strip()} player"
        )
    else:
        parts.append(f"The {candidate.brand} {candidate.name} is a strong match")

    specs = candidate.specs or {}
    detail_bits: list[str] = []
    if specs.get("cut_height"):
        detail_bits.append(f"{str(specs['cut_height']).replace('_', ' ')} cut")
    if specs.get("cushioning_tech"):
        detail_bits.append(f"{specs['cushioning_tech']} cushioning")
    if specs.get("outdoor_suitability"):
        detail_bits.append(
            f"outdoor suitability rated {specs['outdoor_suitability']}"
        )
    if detail_bits:
        parts.append("with " + ", ".join(detail_bits))

    sentence = " ".join(parts) + "."

    if candidate.snippets:
        snippet = candidate.snippets[0]
        quote = _shorten(snippet.text)
        if snippet.source:
            sentence += f' {snippet.source} notes: "{quote}"'
        else:
            sentence += f' From the specs: "{quote}"'

    return sentence


def _shorten(text: str, max_chars: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"
