"""Shared embedding client wrapper — single source for provider/model config.

Both the offline corpus embedder (``pipeline/embed``) and query-time
embedding (``app/services/rag/embedder.py``) go through this client, so the
index and the query are guaranteed to use the same model
(``settings.embedding_model_id``).
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

import httpx

from shared.config import settings
from shared.http import RETRYABLE_STATUSES, retry_delay

logger = logging.getLogger(__name__)

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# OpenAI accepts up to 2048 inputs per request; stay well under the
# per-request token ceiling with review-sized chunks.
MAX_BATCH_SIZE = 100

MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0


class EmbeddingError(RuntimeError):
    """The embeddings API failed after retries or returned a bad payload.

    Every failure mode of ``embed``/``embed_one`` — HTTP errors, transport
    errors (timeouts, connection drops), malformed payloads — surfaces as
    this type, so callers can catch it to trigger the no-vector fallback.
    """


class EmbeddingClient:
    """Thin OpenAI embeddings client: batching + retry, nothing provider-fancy.

    Pass ``http_client`` in tests (e.g. httpx.MockTransport); the default is a
    real client with sane timeouts.
    """

    def __init__(
        self,
        model_id: str | None = None,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        url: str = OPENAI_EMBEDDINGS_URL,
    ) -> None:
        self.model_id = model_id or settings.embedding_model_id
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._url = url
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(30.0))

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in order; one vector per input text."""
        if not self._api_key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not set — add it to backend/.env"
            )
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[start : start + MAX_BATCH_SIZE]))
        return vectors

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        payload = {"model": self.model_id, "input": batch}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._http.post(self._url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "embeddings API request failed (%s), retrying in %.1fs "
                        "(attempt %d/%d)",
                        exc,
                        delay,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue
                raise EmbeddingError(
                    f"embeddings API request failed after retries: {exc}"
                ) from exc
            if response.status_code == 200:
                return self._parse(response, expected=len(batch))
            if response.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                delay = retry_delay(response, attempt, BACKOFF_BASE_SECONDS)
                logger.warning(
                    "embeddings API %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            raise EmbeddingError(
                f"embeddings API returned {response.status_code}: {response.text[:200]}"
            )
        raise EmbeddingError("unreachable")  # pragma: no cover

    def _parse(self, response: httpx.Response, expected: int) -> list[list[float]]:
        try:
            data = response.json().get("data")
            if not isinstance(data, list) or len(data) != expected:
                raise EmbeddingError(
                    f"embeddings API returned {len(data) if isinstance(data, list) else 'no'}"
                    f" vectors for {expected} inputs"
                )
            # API may return out of order; `index` is authoritative.
            ordered = sorted(data, key=lambda item: item["index"])
            return [item["embedding"] for item in ordered]
        except EmbeddingError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            # non-JSON body, or items missing index/embedding keys
            raise EmbeddingError(
                f"embeddings API returned a malformed payload: {exc!r}"
            ) from exc


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    """Default client wired from settings (FastAPI dependency-friendly).

    Cached so every request shares one httpx connection pool instead of
    paying a fresh TCP+TLS handshake per call; tests that need isolation
    can call ``get_embedding_client.cache_clear()``.
    """
    return EmbeddingClient()
