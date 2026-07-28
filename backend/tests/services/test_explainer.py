"""Explainer tests — template path, LLM mapping, and fallback (no live OpenAI)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.schemas.candidate import Candidate, ReviewSnippet
from app.services.rag import explainer, explainer_llm, explainer_template
from shared.llm import LLMClient, LLMError


def _candidates(n: int = 3) -> list[Candidate]:
    return [
        Candidate(
            shoe_id=i,
            brand="Nike",
            name=f"Shoe {i}",
            price=100.0 + i,
            specs={
                "playstyle_tags": ["slasher"],
                "position_tags": ["guard"],
                "cut_height": "low",
                "cushioning_tech": "ZoomX",
            },
            snippets=[
                ReviewSnippet(
                    text="Sticky traction on dusty courts.",
                    source="weartesters",
                )
            ],
            similarity=0.9 - i * 0.1,
        )
        for i in range(n)
    ]


def _llm_client(handler) -> LLMClient:
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


def test_template_explain_picks_top_three_and_builds_chips() -> None:
    recs = explainer_template.explain(_candidates(5)[:3], playstyle="slasher guard")
    assert len(recs) == 3
    assert recs[0].model == "Shoe 0"
    assert recs[0].id == 0
    assert "slasher" in recs[0].specs
    assert "guard" in recs[0].specs
    assert "weartesters" in recs[0].explanation
    assert "Sticky traction" in recs[0].explanation
    assert recs[0].similarity == 0.9


def test_template_explain_empty_candidates() -> None:
    assert explainer_template.explain([]) == []


def test_llm_explain_maps_structured_cards() -> None:
    payload = {
        "cards": [
            {
                "specs": ["slasher", "guard", "low cut"],
                "explanation": "Great for a slasher guard with sticky traction.",
            },
            {
                "specs": ["slasher"],
                "explanation": "Solid secondary pick for containment.",
            },
            {
                "specs": ["guard"],
                "explanation": "Budget-friendly option with ZoomX.",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert "Shopper profile" in body["messages"][1]["content"]
        assert "low profile black" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(payload)}}
                ]
            },
        )

    recs = explainer_llm.explain(
        _candidates(3),
        playstyle="slasher guard",
        aesthetic="low profile black",
        client=_llm_client(handler),
    )
    assert len(recs) == 3
    assert recs[0].specs == ["slasher", "guard", "low cut"]
    assert "sticky traction" in recs[0].explanation
    assert recs[0].id == 0
    assert recs[0].brand == "Nike"
    assert recs[0].similarity == 0.9


def test_llm_explain_length_mismatch_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "cards": [
                                        {
                                            "specs": ["a"],
                                            "explanation": "Only one card.",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    with pytest.raises(LLMError, match="1 cards for 3"):
        explainer_llm.explain(
            _candidates(3),
            client=_llm_client(handler),
        )


def test_public_explain_falls_back_on_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise LLMError("quota")

    monkeypatch.setattr("app.services.rag.explainer_llm.explain", boom)
    recs = explainer.explain(_candidates(2), playstyle="slasher")
    assert len(recs) == 2
    assert "Shoe 0" in recs[0].explanation
    assert recs[0].specs


def test_public_explain_uses_llm_when_available() -> None:
    payload = {
        "cards": [
            {
                "specs": ["custom chip"],
                "explanation": "LLM wrote this explanation.",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(payload)}}
                ]
            },
        )

    recs = explainer.explain(
        _candidates(1),
        playstyle="guard",
        aesthetic="all black",
        client=_llm_client(handler),
    )
    assert recs[0].explanation == "LLM wrote this explanation."
    assert recs[0].specs == ["custom chip"]


def test_build_user_prompt_includes_evidence() -> None:
    text = explainer_llm._build_user_prompt(
        _candidates(1),
        playstyle="slasher",
        aesthetic="",
    )
    assert "Playstyle: slasher" in text
    assert "Aesthetic: (not provided)" in text
    assert "[weartesters] Sticky traction" in text
    assert "Shoe 0" in text
