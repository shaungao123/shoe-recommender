"""Shared scraper machinery: polite fetching, disk cache, robots.txt.

Every source module subclasses :class:`BaseScraper` and implements three
methods — ``list_shoes`` / ``fetch_detail`` / ``parse`` — so a markup change
on one site can never break another. All network behaviour (rate limiting,
retries, caching, robots) lives here and is identical across sources.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
import urllib.robotparser
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from pipeline.schema import SourceRecord

log = logging.getLogger(__name__)

USER_AGENT = (
    "ShoeRecommenderBot/0.1 "
    "(personal research pipeline; mailto:iwpressman@gmail.com)"
)

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

# Politeness knobs — concurrency is 1 by construction (sync client).
MIN_DELAY_SECONDS = 3.0
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 5.0
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    fetched_at: str  # ISO-8601, when the content was actually downloaded
    from_cache: bool


class RobotsPolicy:
    """Fetches and honors robots.txt, one parser per domain per run."""

    def __init__(self, client: httpx.Client):
        self._client = client
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        host = urlsplit(url).netloc
        parser = self._parsers.get(host)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = f"https://{host}/robots.txt"
            try:
                resp = self._client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser.disallow_all = True
                else:  # 404 etc. — everything allowed
                    parser.allow_all = True
            except httpx.HTTPError:
                # Can't read robots — err on the side of not crawling.
                parser.disallow_all = True
            self._parsers[host] = parser
        return parser.can_fetch(USER_AGENT, url)


class DiskCache:
    """Raw HTML/JSON cache keyed by URL so re-runs never re-hit the network."""

    def __init__(self, root: Path = CACHE_DIR):
        self.root = root

    def _paths(self, source: str, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        base = self.root / source
        return base / f"{key}.html", base / f"{key}.meta.json"

    def get(self, source: str, url: str) -> FetchResult | None:
        body_path, meta_path = self._paths(source, url)
        if not (body_path.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return FetchResult(
            url=meta["url"],
            status=meta["status"],
            text=body_path.read_text(encoding="utf-8"),
            fetched_at=meta["fetched_at"],
            from_cache=True,
        )

    def put(self, source: str, result: FetchResult) -> None:
        body_path, meta_path = self._paths(source, result.url)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(result.text, encoding="utf-8")
        meta_path.write_text(
            json.dumps(
                {
                    "url": result.url,
                    "status": result.status,
                    "fetched_at": result.fetched_at,
                }
            ),
            encoding="utf-8",
        )


class Fetcher:
    """Rate-limited, retrying, cached, robots-honoring HTTP GET."""

    def __init__(self, cache: DiskCache | None = None, refresh: bool = False):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )
        self.cache = cache or DiskCache()
        self.refresh = refresh
        self.robots = RobotsPolicy(self.client)
        self._last_request: dict[str, float] = {}  # per-domain monotonic ts

    def _throttle(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = MIN_DELAY_SECONDS + random.uniform(0, 1.0) - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def get(self, source: str, url: str) -> FetchResult | None:
        """Returns None when robots disallows the URL or retries exhaust."""
        if not self.refresh:
            cached = self.cache.get(source, url)
            if cached is not None:
                return cached

        if not self.robots.allowed(url):
            log.warning("robots.txt disallows %s — skipping", url)
            return None

        for attempt in range(MAX_RETRIES):
            self._throttle(url)
            try:
                resp = self.client.get(url)
            except httpx.HTTPError as exc:
                log.warning("fetch error %s (attempt %d): %s", url, attempt + 1, exc)
                time.sleep(BACKOFF_BASE_SECONDS * 2**attempt)
                continue

            if resp.status_code in RETRYABLE_STATUSES:
                retry_after = resp.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else BACKOFF_BASE_SECONDS * 2**attempt
                )
                log.warning(
                    "%s from %s — backing off %.0fs", resp.status_code, url, delay
                )
                time.sleep(delay)
                continue

            result = FetchResult(
                url=url,
                status=resp.status_code,
                text=resp.text,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                from_cache=False,
            )
            if resp.status_code == 200:
                self.cache.put(source, result)
                return result
            log.warning("non-retryable %s from %s — skipping", resp.status_code, url)
            return None

        log.error("giving up on %s after %d attempts", url, MAX_RETRIES)
        return None


@dataclass
class ShoeRef:
    """A shoe found on a listing page, before its detail page is fetched."""

    name: str
    url: str


class BaseScraper(ABC):
    """fetch listing → fetch details → parse → SourceRecords."""

    #: unique short id, used for cache dirs, staging filenames, provenance
    name: str = ""
    base_url: str = ""

    def __init__(self, fetcher: Fetcher | None = None):
        self.fetcher = fetcher or Fetcher()

    # -- per-source implementations ------------------------------------
    @abstractmethod
    def list_shoes(self) -> list[ShoeRef]:
        """Discover every shoe detail URL this source offers."""

    def fetch_detail(self, url: str) -> FetchResult | None:
        return self.fetcher.get(self.name, url)

    @abstractmethod
    def parse(self, html: str, url: str, fetched_at: str) -> SourceRecord | None:
        """Extract a SourceRecord from one detail page (None if unparseable)."""

    # -- shared orchestration -------------------------------------------
    def scrape(self, limit=None, ref_filter=None) -> list[SourceRecord]:
        refs = self.list_shoes()
        if ref_filter is not None:
            refs = [ref for ref in refs if ref_filter(ref)]
        if limit is not None:
            refs = refs[:limit]
        log.info("[%s] %d shoes to fetch", self.name, len(refs))
        records: list[SourceRecord] = []
        for i, ref in enumerate(refs, 1):
            result = self.fetch_detail(ref.url)
            if result is None:
                continue
            try:
                record = self.parse(result.text, result.url, result.fetched_at)
            except Exception:
                log.exception("[%s] parse failed for %s", self.name, ref.url)
                continue
            if record is not None:
                records.append(record)
            if i % 10 == 0:
                log.info("[%s] %d/%d done", self.name, i, len(refs))
        log.info("[%s] parsed %d records", self.name, len(records))
        return records
