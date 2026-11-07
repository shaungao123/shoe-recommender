"""Fill ``shoes.image_url`` from Vertex AI Search (Agent Search) + Supabase Storage.

    python -m pipeline.images.search
    python -m pipeline.images.search --refresh
    python -m pipeline.images.search --limit 5

Searches once per unique brand+name (not once per table row), takes the first
downloadable result (the Vertex AI Search app's website data store is limited
to brand sites), uploads it to the public ``shoe-images`` bucket, and writes the
public URL onto every row that shares that brand+name.

Image search needs a website-search app with Enterprise edition features on and
a single data store. Auth is a Google Cloud service account
(``GOOGLE_APPLICATION_CREDENTIALS``) or other Application Default Credentials.

Nothing else in the pipeline calls this. A scrape / upsert must not spend
search quota or change photos.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from shared.config import settings
from shared.db.models import Shoe

logger = logging.getLogger(__name__)

BUCKET = "shoe-images"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
USER_AGENT = (
    "Mozilla/5.0 (compatible; ShoeRecommenderBot/0.1; "
    "+https://github.com/local/the_assist)"
)
DOWNLOAD_TIMEOUT = 30.0
SEARCH_TIMEOUT = 30.0


@dataclass
class SearchHit:
    title: str
    link: str


@dataclass
class CandidateNote:
    title: str
    link: str
    why: str


@dataclass
class ChosenImage:
    publisher_url: str
    content_type: str
    body: bytes
    rejected: list[CandidateNote] = field(default_factory=list)


@dataclass
class SearchRunResult:
    searched: int = 0
    uploaded: int = 0
    skipped: int = 0
    missed: int = 0
    errors: int = 0


@dataclass
class VertexSearchConfig:
    project_id: str
    app_id: str
    get_token: Callable[[], str]
    location: str = "global"

    @property
    def search_url(self) -> str:
        # Apps in the "us"/"eu" multi-regions are only served from a regional host.
        host = (
            "discoveryengine.googleapis.com"
            if self.location == "global"
            else f"{self.location}-discoveryengine.googleapis.com"
        )
        return (
            f"https://{host}/v1/projects/{self.project_id}"
            f"/locations/{self.location}/collections/default_collection"
            f"/engines/{self.app_id}/servingConfigs/default_search:search"
        )


class VertexSearchError(RuntimeError):
    """Vertex AI Search rejected a request."""

    def __init__(self, status_code: int, message: str, reason: str | None = None):
        self.status_code = status_code
        self.reason = reason
        super().__init__(message)


class VertexSearchFatalError(VertexSearchError):
    """401/403/404/429 — every further search would fail the same way or burn quota."""


def parse_google_api_error(response: httpx.Response) -> tuple[str, str | None]:
    """Return ``(message, reason)`` from a Google API error body."""
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return (text or f"HTTP {response.status_code}", None)
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return (f"HTTP {response.status_code}", None)
    err = payload.get("error") or {}
    message = err.get("message") or f"HTTP {response.status_code}"
    reason = err.get("status")
    errors = err.get("errors") or []
    if errors and isinstance(errors[0], dict) and errors[0].get("reason"):
        reason = errors[0]["reason"]
    return message, reason


def make_token_provider(credentials_file: str = "") -> Callable[[], str]:
    """Access-token callable, refreshed on expiry.

    Uses the service account key at ``credentials_file`` if given, otherwise
    Application Default Credentials.
    """
    import google.auth
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    if credentials_file:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=[CLOUD_PLATFORM_SCOPE]
        )
    else:
        credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])

    def get_token() -> str:
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    return get_token


def ext_for_content_type(content_type: str) -> str:
    ct = content_type.split(";")[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(ct, ".jpg")


def public_object_url(supabase_url: str, object_path: str) -> str:
    base = supabase_url.rstrip("/")
    return f"{base}/storage/v1/object/public/{BUCKET}/{object_path}"


def search_images(
    client: httpx.Client,
    *,
    search: VertexSearchConfig,
    query: str,
) -> list[SearchHit]:
    response = client.post(
        search.search_url,
        headers={
            "Authorization": f"Bearer {search.get_token()}",
            "X-Goog-User-Project": search.project_id,
        },
        json={
            "query": query,
            "pageSize": 10,
            "params": {"search_type": 1},
        },
        timeout=SEARCH_TIMEOUT,
    )
    if response.status_code >= 400:
        message, reason = parse_google_api_error(response)
        detail = message if reason is None else f"{message} (reason={reason})"
        if response.status_code in (401, 403, 404, 429):
            raise VertexSearchFatalError(response.status_code, detail, reason)
        raise VertexSearchError(response.status_code, detail, reason)
    results = response.json().get("results") or []
    hits: list[SearchHit] = []
    for result in results:
        data = (result.get("document") or {}).get("derivedStructData") or {}
        link = data.get("link")
        if not link:
            continue
        hits.append(SearchHit(title=data.get("title") or "", link=link))
    return hits


def download_image(client: httpx.Client, url: str) -> tuple[bytes, str] | None:
    try:
        response = client.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"},
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        logger.warning("download failed for %s: %s", url, exc)
        return None
    if response.status_code != 200:
        logger.warning("download status %s for %s", response.status_code, url)
        return None
    content_type = response.headers.get("content-type", "")
    if not content_type.lower().startswith("image/"):
        logger.warning("non-image content-type %r for %s", content_type, url)
        return None
    if not response.content:
        logger.warning("empty body for %s", url)
        return None
    return response.content, content_type


def choose_downloadable_image(
    client: httpx.Client,
    hits: list[SearchHit],
) -> ChosenImage | None:
    """Try Google's results in order until one downloads as an image."""
    rejected: list[CandidateNote] = []
    for hit in hits:
        downloaded = download_image(client, hit.link)
        if downloaded is None:
            rejected.append(
                CandidateNote(title=hit.title, link=hit.link, why="download_failed")
            )
            continue
        body, content_type = downloaded
        return ChosenImage(
            publisher_url=hit.link,
            content_type=content_type,
            body=body,
            rejected=rejected,
        )
    return None


def upload_to_supabase(
    client: httpx.Client,
    *,
    supabase_url: str,
    service_role_key: str,
    object_path: str,
    body: bytes,
    content_type: str,
) -> str:
    base = supabase_url.rstrip("/")
    upload_url = f"{base}/storage/v1/object/{BUCKET}/{object_path}"
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": content_type.split(";")[0].strip(),
        "x-upsert": "true",
    }
    response = client.post(upload_url, content=body, headers=headers, timeout=DOWNLOAD_TIMEOUT)
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"supabase upload failed status={response.status_code} body={response.text[:300]}"
        )
    return public_object_url(supabase_url, object_path)


def build_image_search_meta(
    *,
    query: str,
    publisher_url: str | None,
    storage_path: str | None,
    public_url: str | None,
    rejected: list[CandidateNote],
    miss: bool,
) -> dict[str, Any]:
    return {
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "publisher_url": publisher_url,
        "storage_path": storage_path,
        "public_url": public_url,
        "miss": miss,
        "rejected": [
            {"title": c.title, "link": c.link, "why": c.why} for c in rejected
        ],
    }


def has_prior_image_search(row: Shoe) -> bool:
    meta = row.extra_metadata or {}
    return "image_search" in meta


def name_key(row: Shoe) -> tuple[str, str]:
    return ((row.brand or "").strip().lower(), (row.name or "").strip().lower())


def group_by_unique_name(rows: list[Shoe]) -> list[list[Shoe]]:
    """Collapse rows that share the same brand+name, preserving first-seen order."""
    groups: dict[tuple[str, str], list[Shoe]] = {}
    order: list[tuple[str, str]] = []
    for row in rows:
        key = name_key(row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    return [groups[key] for key in order]


def apply_image_result(source: Shoe, targets: list[Shoe]) -> None:
    """Copy ``image_url`` and ``image_search`` meta from ``source`` onto each target."""
    meta = (source.extra_metadata or {}).get("image_search")
    for row in targets:
        row.image_url = source.image_url
        row.extra_metadata = {**(row.extra_metadata or {}), "image_search": meta}


def process_shoe(
    session: Session,
    client: httpx.Client,
    row: Shoe,
    *,
    search: VertexSearchConfig,
    supabase_url: str,
    service_role_key: str,
) -> str:
    """Search, upload, and update one shoe. Returns 'uploaded' | 'missed'."""
    assert row.canonical_id is not None
    query = f"{row.brand} {row.name} basketball shoe"
    hits = search_images(client, search=search, query=query)
    if not hits:
        meta = build_image_search_meta(
            query=query,
            publisher_url=None,
            storage_path=None,
            public_url=None,
            rejected=[],
            miss=True,
        )
        row.extra_metadata = {**(row.extra_metadata or {}), "image_search": meta}
        return "missed"

    chosen = choose_downloadable_image(client, hits)
    if chosen is None:
        rejected = [
            CandidateNote(title=h.title, link=h.link, why="download_failed")
            for h in hits
        ]
        meta = build_image_search_meta(
            query=query,
            publisher_url=None,
            storage_path=None,
            public_url=None,
            rejected=rejected,
            miss=True,
        )
        row.extra_metadata = {**(row.extra_metadata or {}), "image_search": meta}
        return "missed"

    ext = ext_for_content_type(chosen.content_type)
    object_path = f"{row.canonical_id}{ext}"
    public_url = upload_to_supabase(
        client,
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        object_path=object_path,
        body=chosen.body,
        content_type=chosen.content_type,
    )
    meta = build_image_search_meta(
        query=query,
        publisher_url=chosen.publisher_url,
        storage_path=f"{BUCKET}/{object_path}",
        public_url=public_url,
        rejected=chosen.rejected,
        miss=False,
    )
    row.image_url = public_url
    row.extra_metadata = {**(row.extra_metadata or {}), "image_search": meta}
    return "uploaded"


def run_search(
    session: Session,
    client: httpx.Client,
    *,
    refresh: bool,
    limit: int | None,
    search: VertexSearchConfig,
    supabase_url: str,
    service_role_key: str,
) -> SearchRunResult:
    result = SearchRunResult()
    rows = list(
        session.scalars(
            select(Shoe)
            .where(Shoe.canonical_id.is_not(None))
            .order_by(Shoe.canonical_id)
        )
    )
    for group in group_by_unique_name(rows):
        if limit is not None and result.searched >= limit:
            break
        primary = group[0]
        siblings = group[1:]
        canonical_id = primary.canonical_id
        if not refresh and any(has_prior_image_search(row) for row in group):
            donor = next(row for row in group if has_prior_image_search(row))
            apply_image_result(donor, [row for row in group if row is not donor])
            session.commit()
            result.skipped += 1
            continue
        result.searched += 1
        try:
            outcome = process_shoe(
                session,
                client,
                primary,
                search=search,
                supabase_url=supabase_url,
                service_role_key=service_role_key,
            )
            if siblings:
                apply_image_result(primary, siblings)
            if outcome == "uploaded":
                result.uploaded += 1
            else:
                result.missed += 1
            session.commit()
        except VertexSearchFatalError as exc:
            session.rollback()
            result.errors += 1
            logger.error(
                "Vertex AI Search %s for %s — stopping run: %s",
                exc.status_code,
                canonical_id,
                exc,
            )
            break
        except Exception:
            session.rollback()
            result.errors += 1
            logger.exception("failed for %s", canonical_id)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.images.search", description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-query shoes that already have extra_metadata.image_search",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="max number of unique brand+name image searches this run",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project),
            ("VERTEX_SEARCH_APP_ID", settings.vertex_search_app_id),
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
        )
        if not value
    ]
    if missing:
        logger.error("missing required settings: %s", ", ".join(missing))
        return 1

    if settings.database_url.startswith("sqlite"):
        logger.error(
            "database_url is the SQLite fallback (%s) — set the Postgres URL "
            "in backend/.env before searching for images",
            settings.database_url,
        )
        return 1

    import google.auth.exceptions

    try:
        get_token = make_token_provider(settings.google_application_credentials)
    except (google.auth.exceptions.DefaultCredentialsError, OSError, ValueError) as exc:
        logger.error(
            "no Google Cloud credentials — set GOOGLE_APPLICATION_CREDENTIALS to a "
            "service account JSON key path: %s",
            exc,
        )
        return 1
    search = VertexSearchConfig(
        project_id=settings.google_cloud_project,
        app_id=settings.vertex_search_app_id,
        location=settings.vertex_search_location,
        get_token=get_token,
    )

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with Session(engine) as session, httpx.Client() as client:
        result = run_search(
            session,
            client,
            refresh=args.refresh,
            limit=args.limit,
            search=search,
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )

    logger.info(
        "searched=%d uploaded=%d missed=%d skipped=%d errors=%d",
        result.searched,
        result.uploaded,
        result.missed,
        result.skipped,
        result.errors,
    )
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
