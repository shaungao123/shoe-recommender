"""Shared HTTP retry policy — one definition of "retryable" and backoff timing.

Used by the scraper fetcher (``pipeline/scrapers/base.py``) and the embedding
client (``shared/embedding/client.py``); each keeps its own retry count and
base delay, but what counts as retryable and how Retry-After is honored must
not drift between them.
"""

from __future__ import annotations

import httpx

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def retry_delay(response: httpx.Response, attempt: int, base_seconds: float) -> float:
    """Server's Retry-After when parseable (floored at 1s), else exponential backoff."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass  # HTTP-date form — fall through to backoff
    return base_seconds * (2**attempt)
