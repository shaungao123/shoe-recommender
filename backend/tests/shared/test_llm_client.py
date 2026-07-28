"""LLM client tests — httpx MockTransport, no network."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from shared.llm.client import LLMClient, LLMError


def make_client(
    handler: httpx.MockTransport | Callable[[httpx.Request], httpx.Response],
) -> LLMClient:
    transport = (
        handler
        if isinstance(handler, httpx.MockTransport)
        else httpx.MockTransport(handler)
    )
    return LLMClient(
        model_id="test-llm",
        api_key="sk-test",
        http_client=httpx.Client(transport=transport),
    )


def ok_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "test-llm"
    assert body["response_format"]["json_schema"]["name"] == "GeneratedBatch"
    assert body["messages"][0]["role"] == "system"
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"cards": [{"specs": ["a"], "explanation": "hi"}]}
                        )
                    }
                }
            ]
        },
    )


def test_complete_json_parses_message_content() -> None:
    client = make_client(ok_response)
    result = client.complete_json(
        system="sys",
        user="usr",
        schema_name="GeneratedBatch",
        schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    assert result == {"cards": [{"specs": ["a"], "explanation": "hi"}]}


def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    import shared.llm.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda _s: None)
    attempts: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return ok_response(request)

    client = make_client(flaky)
    assert client.complete_json(
        system="s",
        user="u",
        schema_name="GeneratedBatch",
        schema={},
    )["cards"]
    assert len(attempts) == 2


def test_non_retryable_error_raises() -> None:
    client = make_client(lambda request: httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(LLMError, match="400"):
        client.complete_json(system="s", user="u", schema_name="X", schema={})


def test_missing_api_key_raises() -> None:
    client = LLMClient(model_id="m", api_key="")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        client.complete_json(system="s", user="u", schema_name="X", schema={})


def test_malformed_payload_raises() -> None:
    client = make_client(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "not-json"}}]}
        )
    )
    with pytest.raises(LLMError, match="malformed"):
        client.complete_json(system="s", user="u", schema_name="X", schema={})
