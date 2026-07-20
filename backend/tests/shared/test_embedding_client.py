"""Embedding client tests — httpx MockTransport, no network."""

from collections.abc import Callable

import httpx
import pytest

from shared.embedding.client import MAX_BATCH_SIZE, EmbeddingClient, EmbeddingError


def make_client(
    handler: httpx.MockTransport | Callable[[httpx.Request], httpx.Response],
) -> EmbeddingClient:
    transport = handler if isinstance(handler, httpx.MockTransport) else httpx.MockTransport(handler)
    return EmbeddingClient(
        model_id="test-model",
        api_key="sk-test",
        http_client=httpx.Client(transport=transport),
    )


def ok_response(request: httpx.Request) -> httpx.Response:
    import json

    inputs = json.loads(request.content)["input"]
    data = [
        {"index": i, "embedding": [float(i), 0.0, 0.0]} for i in range(len(inputs))
    ]
    return httpx.Response(200, json={"data": data})


def test_embed_returns_one_vector_per_text() -> None:
    client = make_client(ok_response)
    vectors = client.embed(["a", "b", "c"])
    assert len(vectors) == 3
    assert vectors[1] == [1.0, 0.0, 0.0]


def test_embed_reorders_by_index() -> None:
    def shuffled(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [1.0]},
                    {"index": 0, "embedding": [0.0]},
                ]
            },
        )

    client = make_client(shuffled)
    assert client.embed(["a", "b"]) == [[0.0], [1.0]]


def test_embed_batches_large_inputs() -> None:
    calls: list[int] = []

    def counting(request: httpx.Request) -> httpx.Response:
        import json

        calls.append(len(json.loads(request.content)["input"]))
        return ok_response(request)

    client = make_client(counting)
    vectors = client.embed(["x"] * (MAX_BATCH_SIZE + 5))
    assert len(vectors) == MAX_BATCH_SIZE + 5
    assert calls == [MAX_BATCH_SIZE, 5]


def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    import shared.embedding.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda _s: None)
    attempts: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return ok_response(request)

    client = make_client(flaky)
    assert len(client.embed(["a"])) == 1
    assert len(attempts) == 2


def test_non_retryable_error_raises() -> None:
    client = make_client(lambda request: httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(EmbeddingError, match="400"):
        client.embed(["a"])


def test_transport_error_retries_then_raises_embedding_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shared.embedding.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda _s: None)
    attempts: list[int] = []

    def dropping(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ConnectError("connection dropped")

    client = make_client(dropping)
    with pytest.raises(EmbeddingError, match="request failed"):
        client.embed(["a"])
    assert len(attempts) == client_module.MAX_RETRIES + 1


def test_transport_error_then_success_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    import shared.embedding.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda _s: None)
    attempts: list[int] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("slow")
        return ok_response(request)

    client = make_client(flaky)
    assert len(client.embed(["a"])) == 1


def test_malformed_payload_raises_embedding_error() -> None:
    # right count, but items missing the 'index' key
    client = make_client(
        lambda request: httpx.Response(200, json={"data": [{"embedding": [0.0]}]})
    )
    with pytest.raises(EmbeddingError, match="malformed"):
        client.embed(["a"])


def test_non_json_body_raises_embedding_error() -> None:
    client = make_client(lambda request: httpx.Response(200, text="<html>gateway</html>"))
    with pytest.raises(EmbeddingError, match="malformed"):
        client.embed(["a"])


def test_missing_api_key_raises() -> None:
    client = EmbeddingClient(
        model_id="test-model",
        api_key="",
        http_client=httpx.Client(transport=httpx.MockTransport(ok_response)),
    )
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        client.embed(["a"])


def test_wrong_vector_count_raises() -> None:
    client = make_client(lambda request: httpx.Response(200, json={"data": []}))
    with pytest.raises(EmbeddingError, match="0 vectors"):
        client.embed(["a"])
