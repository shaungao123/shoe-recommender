"""Generation stage: LLM explanations with deterministic template fallback.

Takes the ranked Candidate list only — never queries the DB. Tries a grounded
structured LLM call first; on ``LLMError`` falls back to the template explainer
so /recommend keeps working without a live chat API.
"""

from __future__ import annotations

import logging

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendedShoe
from app.services.rag import explainer_llm, explainer_template
from shared.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)


def explain(
    candidates: list[Candidate],
    *,
    playstyle: str = "",
    aesthetic: str = "",
    client: LLMClient | None = None,
) -> list[RecommendedShoe]:
    """Build recommendation cards for pre-selected candidates (typically ≤3)."""
    if not candidates:
        return []
    try:
        return explainer_llm.explain(
            candidates,
            playstyle=playstyle,
            aesthetic=aesthetic,
            client=client,
        )
    except LLMError as exc:
        logger.warning("LLM explain failed; using template fallback: %s", exc)
        return explainer_template.explain(candidates, playstyle=playstyle)
