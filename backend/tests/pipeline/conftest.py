"""Offline fixtures: scrapers run against saved HTML, never the network."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.scrapers.base import FetchResult

FIXTURES = Path(__file__).parent / "fixtures"

FETCHED_AT = "2026-07-04T00:00:00+00:00"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeFetcher:
    """Maps URLs to fixture files; any unmapped URL returns None (like a 404)."""

    def __init__(self, url_map: dict[str, str]):
        self.url_map = url_map
        self.requested: list[str] = []

    def get(self, source: str, url: str) -> FetchResult | None:
        self.requested.append(url)
        name = self.url_map.get(url)
        if name is None:
            return None
        return FetchResult(
            url=url,
            status=200,
            text=load_fixture(name),
            fetched_at=FETCHED_AT,
            from_cache=True,
        )


@pytest.fixture
def fake_fetcher():
    return FakeFetcher
