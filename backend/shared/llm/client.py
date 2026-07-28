"""Thin OpenAI Chat Completions client for structured JSON generation.

Mirrors ``shared.embedding.client``: httpx + retries, no SDK. Used by the
RAG explainer for grounded recommendation cards.
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any

import httpx

from shared.config import settings
from shared.http import RETRYABLE_STATUSES, retry_delay

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0


class LLMError(RuntimeError):
    """Chat Completions failed after retries or returned a bad payload.

    Callers catch this to fall back to the deterministic template explainer.
    """


class LLMClient:
    """OpenAI chat client with JSON-schema structured outputs.

    Pass ``http_client`` in tests (e.g. httpx.MockTransport).
    """

    def __init__(
        self,
        model_id: str | None = None,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        url: str = OPENAI_CHAT_URL,
    ) -> None:
        self.model_id = model_id or settings.llm_model_id
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._url = url
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(60.0))

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the parsed JSON object from a structured chat completion."""
        if not self._api_key:
            raise LLMError("OPENAI_API_KEY is not set — add it to backend/.env")

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._http.post(self._url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                if attempt < MAX_RETRIES:
                    delay = BACKOFF_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "chat API request failed (%s), retrying in %.1fs "
                        "(attempt %d/%d)",
                        exc,
                        delay,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue
                raise LLMError(
                    f"chat API request failed after retries: {exc}"
                ) from exc
            if response.status_code == 200:
                return self._parse(response)
            if response.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
                delay = retry_delay(response, attempt, BACKOFF_BASE_SECONDS)
                logger.warning(
                    "chat API %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            raise LLMError(
                f"chat API returned {response.status_code}: {response.text[:200]}"
            )
        raise LLMError("unreachable")  # pragma: no cover

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise LLMError("chat API returned non-string message content")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise LLMError("chat API JSON content was not an object")
            return parsed
        except LLMError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMError(
                f"chat API returned a malformed payload: {exc!r}"
            ) from exc


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Default client wired from settings (FastAPI dependency-friendly)."""
    return LLMClient()
