"""Candidate — the retrieval→generation seam object.

The retriever returns a ranked ``list[Candidate]``; the explainer consumes it
and nothing else (it never queries the DB). Keep this shape stable; if it must
change, update retriever, explainer, and their tests together (see
.claude/rules/rag-pipeline.md).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ReviewSnippet(BaseModel):
    """A retrieved text chunk with provenance for source-credited explanations."""

    text: str
    # Scrape source the chunk came from (e.g. "weartesters"); None means the
    # synthesized spec-summary chunk. basketballshoespecs content must be
    # credited when cited — the explainer uses this field for that.
    source: str | None = None


class Candidate(BaseModel):
    """One retrieved shoe: structured fields + the review snippets that matched.

    Everything the explainer is allowed to say about a shoe must come from
    these fields — grounding depends on this object being complete.
    """

    model_config = ConfigDict(from_attributes=True)

    shoe_id: int
    canonical_id: str | None = None
    brand: str
    name: str
    price: float
    currency: str = "USD"
    image_url: str | None = None
    affiliate_url: str | None = None
    # Structured specs from the shoes table (cut_height, cushioning_tech,
    # playstyle_tags, ...) — same keys as pipeline SPEC_FIELDS.
    specs: dict[str, Any] = {}
    # Best-matching chunks for this query, most relevant first.
    snippets: list[ReviewSnippet] = []
    # Cosine similarity of the best-matching chunk, clamped to [0, 1]
    # (higher = better). None when the candidate came from the no-vector
    # fallback path — a real-but-terrible vector match is 0.0, not None.
    similarity: float | None = None
    # Fallback-only: tag overlap count for primary rank before random tie-break.
    tag_overlap: int | None = None
