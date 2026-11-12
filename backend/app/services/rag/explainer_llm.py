"""LLM-backed grounded explanations for retrieved candidates.

One Chat Completions call with JSON-schema structured output for all ≤3
candidates. Identity fields (id, brand, price, …) always come from the
Candidate — the model only fills specs chips and explanation prose.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.candidate import Candidate
from app.schemas.recommend import EvidenceSnippet, RecommendedShoe
from shared.llm import LLMClient, LLMError, get_llm_client

SYSTEM_PROMPT = """\
You are a basketball shoe recommender. Given a shopper profile and up to 3
retrieved shoe candidates (structured specs + review snippets), write a short
recommendation card for each shoe.

Rules:
- Use ONLY facts present in the provided specs and snippets. Do not invent
  cushioning tech, traction, durability, fit, or court suitability.
- If you quote a review snippet, credit its source (e.g. weartesters).
- Tie each explanation to the shopper's playstyle and aesthetic when provided.
- Keep explanations to 1–3 sentences (under ~400 characters).
- specs: up to 6 short display chips derived from the shoe's tags/specs
  (e.g. "slasher", "guard", "low cut", "ZoomX"). Prefer human-readable
  wording; replace underscores with spaces.
- Return one card per candidate, in the same order as the input list.
- If evidence is thin, say the shoe is a solid match for the stated criteria
  without fabricating details.
- "Why it ranked" lists the facts that put this shoe in the shopper's top 3.
  Lead with the one most relevant to what the shopper asked for.
- These are the shopper's picks: if the evidence shows a weakness for their
  needs, mention it briefly as a caveat; never tell them to look elsewhere.
- Do not make health or injury claims (e.g. about recovery or preventing
  sprains); describe the shoe's support or stability instead.
"""

# Strict JSON schema for OpenAI response_format (additionalProperties: false).
GENERATED_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "specs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["specs", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


class GeneratedCard(BaseModel):
    specs: list[str] = Field(default_factory=list)
    explanation: str

    @field_validator("specs")
    @classmethod
    def _cap_specs(cls, value: list[str]) -> list[str]:
        return [str(s).strip() for s in value if str(s).strip()][:6]

    @field_validator("explanation")
    @classmethod
    def _trim_explanation(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("explanation must be non-empty")
        if len(cleaned) > 400:
            return cleaned[:399].rstrip() + "…"
        return cleaned


class GeneratedBatch(BaseModel):
    cards: list[GeneratedCard]


def explain(
    candidates: list[Candidate],
    *,
    playstyle: str = "",
    aesthetic: str = "",
    client: LLMClient | None = None,
) -> list[RecommendedShoe]:
    """Call the LLM and map structured cards onto candidates by index."""
    if not candidates:
        return []

    llm = client or get_llm_client()
    raw = llm.complete_json(
        system=SYSTEM_PROMPT,
        user=_build_user_prompt(candidates, playstyle=playstyle, aesthetic=aesthetic),
        schema_name="GeneratedBatch",
        schema=GENERATED_BATCH_SCHEMA,
    )
    try:
        batch = GeneratedBatch.model_validate(raw)
    except Exception as exc:
        raise LLMError(f"LLM JSON failed validation: {exc}") from exc

    if len(batch.cards) != len(candidates):
        raise LLMError(
            f"LLM returned {len(batch.cards)} cards for {len(candidates)} candidates"
        )

    return [
        RecommendedShoe(
            id=candidate.shoe_id,
            brand=candidate.brand,
            model=candidate.name,
            price=candidate.price,
            image_url=candidate.image_url,
            affiliate_url=candidate.affiliate_url,
            specs=card.specs,
            explanation=card.explanation,
            evidence=[
                EvidenceSnippet(source=snippet.source, text=_shorten_evidence(snippet.text))
                for snippet in candidate.snippets[:2]
                if _shorten_evidence(snippet.text)
            ],
            similarity=candidate.similarity,
            match_reasons=candidate.match_reasons,
        )
        for candidate, card in zip(candidates, batch.cards, strict=True)
    ]


def _build_user_prompt(
    candidates: list[Candidate],
    *,
    playstyle: str,
    aesthetic: str,
) -> str:
    playstyle_line = playstyle.strip() or "(not provided)"
    aesthetic_line = aesthetic.strip() or "(not provided)"
    lines = [
        "Shopper profile:",
        f"- Playstyle: {playstyle_line}",
        f"- Aesthetic: {aesthetic_line}",
        "",
        "Candidates (explain each in order):",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        price = f"${candidate.price:g}" if candidate.price is not None else "price unavailable"
        lines.append(f"[{index}] {candidate.brand} {candidate.name} — {price}")
        lines.append(f"Specs JSON: {json.dumps(candidate.specs or {}, sort_keys=True)}")
        if candidate.match_reasons:
            lines.append(f"Why it ranked: {'; '.join(candidate.match_reasons)}")
        if candidate.similarity is not None:
            lines.append(f"Similarity: {candidate.similarity:.2f}")
        else:
            lines.append("Similarity: (not available)")
        lines.append("Evidence:")
        if candidate.snippets:
            for snippet in candidate.snippets[:3]:
                source = snippet.source or "specs"
                text = " ".join(snippet.text.split())
                lines.append(f"- [{source}] {text}")
        else:
            lines.append("- (no review snippets)")
        lines.append("")
    lines.append("Produce one recommendation card per candidate in the same order.")
    return "\n".join(lines)


def _shorten_evidence(text: str, max_chars: int = 180) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= max_chars else cleaned[: max_chars - 1].rstrip() + "…"
