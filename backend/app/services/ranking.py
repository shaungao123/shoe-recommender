"""Top-N selection with seeded random tie-break among equal primary ranks.

Primary rank is vector similarity (rounded) or fallback tag overlap. Same
request fingerprint yields the same random sample among ties (stable UX, testable).
"""

from __future__ import annotations

import hashlib
import json
import random

from app.schemas.candidate import Candidate
from app.schemas.recommend import RecommendRequest

SIMILARITY_DECIMALS = 4


def request_seed(request: RecommendRequest) -> int:
    """Stable int seed from all request fields (sorted JSON → sha256)."""
    payload = request.model_dump(mode="json")
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _primary_key(candidate: Candidate) -> float | int:
    if candidate.similarity is not None:
        return round(candidate.similarity, SIMILARITY_DECIMALS)
    return candidate.tag_overlap if candidate.tag_overlap is not None else 0


def select_top_candidates(
    candidates: list[Candidate], n: int, seed: int
) -> list[Candidate]:
    """Pick up to ``n`` candidates; random sample within tied primary ranks."""
    if not candidates or n <= 0:
        return []

    rng = random.Random(seed)
    ordered = sorted(
        candidates,
        key=lambda c: (_primary_key(c), c.shoe_id),
        reverse=True,
    )

    selected: list[Candidate] = []
    index = 0
    while index < len(ordered) and len(selected) < n:
        key = _primary_key(ordered[index])
        group: list[Candidate] = []
        while index < len(ordered) and _primary_key(ordered[index]) == key:
            group.append(ordered[index])
            index += 1
        slots = n - len(selected)
        if len(group) <= slots:
            selected.extend(group)
        else:
            selected.extend(rng.sample(group, slots))
    return selected
