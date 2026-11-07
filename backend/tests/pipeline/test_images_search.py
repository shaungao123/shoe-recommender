"""Unit tests for pipeline.images.search — no network, no Supabase."""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pipeline.images.search import (
    SearchHit,
    VertexSearchConfig,
    VertexSearchFatalError,
    choose_downloadable_image,
    group_by_unique_name,
    has_prior_image_search,
    normalize_for_match,
    parse_google_api_error,
    public_object_url,
    run_search,
    search_images,
    select_hits_for_name,
)
from shared.db.models import Shoe

SEARCH = VertexSearchConfig(project_id="proj", app_id="shoes-app", get_token=lambda: "tok")


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Shoe.__table__.create(engine)
    with Session(engine) as db:
        yield db


def _shoe(**kwargs) -> Shoe:
    defaults = dict(
        canonical_id="adidas-dame-9",
        brand="Adidas",
        name="Dame 9",
        price=Decimal("120.00"),
        currency="USD",
        image_url=None,
        specs={},
        extra_metadata={},
    )
    defaults.update(kwargs)
    return Shoe(**defaults)


# -- download selection ------------------------------------------------


def test_choose_skips_non_image_then_takes_next_hit():
    def handler(request: httpx.Request) -> httpx.Response:
        if "broken" in str(request.url):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")
        return httpx.Response(
            200, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8fakejpeg"
        )

    transport = httpx.MockTransport(handler)
    hits = [
        SearchHit("broken", "https://assets.adidas.com/broken.jpg"),
        SearchHit("ok", "https://assets.adidas.com/dame.jpg"),
    ]
    with httpx.Client(transport=transport) as client:
        chosen = choose_downloadable_image(client, hits)
    assert chosen is not None
    assert chosen.publisher_url == "https://assets.adidas.com/dame.jpg"
    assert chosen.content_type.startswith("image/jpeg")
    assert [c.why for c in chosen.rejected] == ["download_failed"]
    assert chosen.rejected[0].link.endswith("broken.jpg")


def test_choose_returns_none_when_every_download_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    hits = [
        SearchHit("a", "https://cdn.example.com/a.jpg"),
        SearchHit("b", "https://nike.com/b.jpg"),
    ]
    with httpx.Client(transport=transport) as client:
        assert choose_downloadable_image(client, hits) is None


def test_choose_takes_first_downloadable_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8fakejpeg"
        )

    transport = httpx.MockTransport(handler)
    hits = [
        SearchHit("first", "https://nike.com/first.jpg"),
        SearchHit("second", "https://nike.com/second.jpg"),
    ]
    with httpx.Client(transport=transport) as client:
        chosen = choose_downloadable_image(client, hits)
    assert chosen is not None
    assert chosen.publisher_url == "https://nike.com/first.jpg"


def test_public_object_url():
    assert (
        public_object_url("https://proj.supabase.co", "nike-sabrina-2.jpg")
        == "https://proj.supabase.co/storage/v1/object/public/shoe-images/nike-sabrina-2.jpg"
    )


# -- skip / refresh ----------------------------------------------------


def test_has_prior_image_search():
    assert not has_prior_image_search(_shoe())
    assert has_prior_image_search(
        _shoe(extra_metadata={"image_search": {"query": "x", "miss": True}})
    )


def test_parse_google_api_error_extracts_reason():
    response = httpx.Response(
        403,
        json={
            "error": {
                "message": "Daily Limit Exceeded",
                "errors": [{"reason": "dailyLimitExceeded", "domain": "usageLimits"}],
            }
        },
    )
    message, reason = parse_google_api_error(response)
    assert message == "Daily Limit Exceeded"
    assert reason == "dailyLimitExceeded"


def test_parse_google_api_error_falls_back_to_status():
    response = httpx.Response(
        403,
        json={
            "error": {
                "code": 403,
                "message": "Permission denied on resource project proj.",
                "status": "PERMISSION_DENIED",
            }
        },
    )
    message, reason = parse_google_api_error(response)
    assert message == "Permission denied on resource project proj."
    assert reason == "PERMISSION_DENIED"


def test_search_images_posts_image_search_and_parses_results():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["project"] = request.headers["x-goog-user-project"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "document": {
                            "derivedStructData": {
                                "title": "Dame 9",
                                "link": "https://assets.adidas.com/dame9.jpg",
                            }
                        }
                    },
                    {"document": {"derivedStructData": {"title": "no link"}}},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        hits = search_images(client, search=SEARCH, query="Adidas Dame 9")

    assert hits == [SearchHit("Dame 9", "https://assets.adidas.com/dame9.jpg")]
    assert seen["url"] == (
        "https://discoveryengine.googleapis.com/v1/projects/proj/locations/global"
        "/collections/default_collection/engines/shoes-app"
        "/servingConfigs/default_search:search"
    )
    assert seen["auth"] == "Bearer tok"
    assert seen["project"] == "proj"
    assert seen["body"]["query"] == "Adidas Dame 9"
    assert seen["body"]["params"] == {"search_type": 1}


def test_search_url_uses_regional_host_outside_global():
    eu = VertexSearchConfig(
        project_id="proj", app_id="shoes-app", location="eu", get_token=lambda: "tok"
    )
    assert eu.search_url.startswith(
        "https://eu-discoveryengine.googleapis.com/v1/projects/proj/locations/eu/"
    )


def test_search_images_raises_fatal_error_on_403():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "message": "Permission denied",
                    "status": "PERMISSION_DENIED",
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VertexSearchFatalError) as excinfo:
            search_images(client, search=SEARCH, query="Adidas Dame 9")
    assert excinfo.value.status_code == 403
    assert "PERMISSION_DENIED" in str(excinfo.value)


def test_group_by_unique_name_collapses_duplicates():
    a = _shoe(canonical_id="nike-sabrina-2-a", brand="Nike", name="Sabrina 2")
    b = _shoe(canonical_id="nike-sabrina-2-b", brand="nike", name=" Sabrina 2 ")
    c = _shoe(canonical_id="adidas-dame-9", brand="Adidas", name="Dame 9")
    groups = group_by_unique_name([a, b, c])
    assert len(groups) == 2
    assert [row.canonical_id for row in groups[0]] == [
        "nike-sabrina-2-a",
        "nike-sabrina-2-b",
    ]
    assert [row.canonical_id for row in groups[1]] == ["adidas-dame-9"]


def test_run_search_skips_existing_unless_refresh(session, monkeypatch):
    row = _shoe(
        extra_metadata={"image_search": {"query": "already done", "miss": False}}
    )
    session.add(row)
    session.commit()

    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not search")

    monkeypatch.setattr("pipeline.images.search.process_shoe", boom)

    with httpx.Client() as client:
        result = run_search(
            session,
            client,
            refresh=False,
            limit=None,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )
    assert result.skipped == 1
    assert result.searched == 0
    assert called["n"] == 0

    def fake_process(session, client, row, **kwargs):
        return "uploaded"

    monkeypatch.setattr("pipeline.images.search.process_shoe", fake_process)
    with httpx.Client() as client:
        refreshed = run_search(
            session,
            client,
            refresh=True,
            limit=None,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )
    assert refreshed.searched == 1
    assert refreshed.uploaded == 1


def test_run_search_stops_on_quota_error(session, monkeypatch):
    first = _shoe(canonical_id="adidas-dame-8", brand="Adidas", name="Dame 8")
    second = _shoe(canonical_id="adidas-dame-9", brand="Adidas", name="Dame 9")
    session.add_all([first, second])
    session.commit()

    called: list[str] = []

    def fake_process(session, client, row, **kwargs):
        called.append(row.canonical_id)
        raise VertexSearchFatalError(429, "Rate Limit Exceeded (reason=rateLimitExceeded)", "rateLimitExceeded")

    monkeypatch.setattr("pipeline.images.search.process_shoe", fake_process)

    with httpx.Client() as client:
        result = run_search(
            session,
            client,
            refresh=False,
            limit=None,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )

    assert called == ["adidas-dame-8"]
    assert result.searched == 1
    assert result.errors == 1
    assert result.uploaded == 0


def test_run_search_once_per_unique_name_and_copies_to_siblings(session, monkeypatch):
    primary = _shoe(
        canonical_id="nike-sabrina-2-a", brand="Nike", name="Sabrina 2"
    )
    sibling = _shoe(
        canonical_id="nike-sabrina-2-b", brand="Nike", name="Sabrina 2"
    )
    other = _shoe(canonical_id="adidas-dame-9", brand="Adidas", name="Dame 9")
    session.add_all([primary, sibling, other])
    session.commit()

    called: list[str] = []

    def fake_process(session, client, row, **kwargs):
        called.append(row.canonical_id)
        row.image_url = f"https://cdn.example/{row.canonical_id}.jpg"
        row.extra_metadata = {
            **(row.extra_metadata or {}),
            "image_search": {"query": f"{row.brand} {row.name}", "miss": False},
        }
        return "uploaded"

    monkeypatch.setattr("pipeline.images.search.process_shoe", fake_process)

    with httpx.Client() as client:
        result = run_search(
            session,
            client,
            refresh=False,
            limit=None,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )

    assert result.searched == 2
    assert result.uploaded == 2
    assert called == ["adidas-dame-9", "nike-sabrina-2-a"]

    rows = {
        row.canonical_id: row
        for row in session.scalars(select(Shoe)).all()
    }
    assert rows["nike-sabrina-2-a"].image_url == (
        "https://cdn.example/nike-sabrina-2-a.jpg"
    )
    assert rows["nike-sabrina-2-b"].image_url == (
        "https://cdn.example/nike-sabrina-2-a.jpg"
    )
    assert rows["nike-sabrina-2-b"].extra_metadata["image_search"]["query"] == (
        "Nike Sabrina 2"
    )
    assert rows["adidas-dame-9"].image_url == "https://cdn.example/adidas-dame-9.jpg"


def test_process_shoe_uploads_by_canonical_id(session, monkeypatch):
    from pipeline.images import search as search_mod

    row = _shoe(canonical_id="nike-sabrina-2", brand="Nike", name="Sabrina 2")
    session.add(row)
    session.commit()

    monkeypatch.setattr(
        search_mod,
        "search_images",
        lambda *a, **k: [
            SearchHit("Nike Sabrina 3", "https://static.nike.com/sabrina3.jpg"),
            SearchHit("Sabrina 2 EP", "https://static.nike.com/sabrina.jpg"),
            SearchHit("Sabrina 2 colorways", "https://static.nike.com/other.jpg"),
        ],
    )

    def fake_choose(client, hits):
        assert hits[0].link == "https://static.nike.com/sabrina.jpg"
        return search_mod.ChosenImage(
            publisher_url="https://static.nike.com/sabrina.jpg",
            content_type="image/jpeg",
            body=b"\xff\xd8data",
            rejected=[],
        )

    monkeypatch.setattr(search_mod, "choose_downloadable_image", fake_choose)

    uploaded: dict[str, str] = {}

    def fake_upload(client, **kwargs):
        uploaded["path"] = kwargs["object_path"]
        assert kwargs["object_path"] == "nike-sabrina-2.jpg"
        return public_object_url(kwargs["supabase_url"], kwargs["object_path"])

    monkeypatch.setattr(search_mod, "upload_to_supabase", fake_upload)

    with httpx.Client() as client:
        outcome = search_mod.process_shoe(
            session,
            client,
            row,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )
    session.commit()

    assert outcome == "uploaded"
    assert uploaded["path"] == "nike-sabrina-2.jpg"
    refreshed = session.scalars(select(Shoe)).one()
    assert refreshed.image_url == (
        "https://proj.supabase.co/storage/v1/object/public/shoe-images/nike-sabrina-2.jpg"
    )
    assert refreshed.extra_metadata["image_search"]["publisher_url"] == (
        "https://static.nike.com/sabrina.jpg"
    )
    assert refreshed.extra_metadata["image_search"]["storage_path"] == (
        "shoe-images/nike-sabrina-2.jpg"
    )
    assert [r["why"] for r in refreshed.extra_metadata["image_search"]["rejected"]] == [
        "name_mismatch"
    ]


# -- name matching -----------------------------------------------------


def test_normalize_for_match_splits_letters_and_digits():
    assert normalize_for_match("AG5") == "ag 5"
    assert normalize_for_match("ag-5") == "ag 5"
    assert normalize_for_match("AG 5: Aaron Gordon’s") == "ag 5 aaron gordon s"


def test_select_hits_drops_neighbouring_models_and_prefers_product_pages():
    hits = [
        SearchHit("AG 6: AG Ion", "https://x/ag6.png", "https://www.361usa.com/products/ag-6-ag-ion"),
        SearchHit(
            "Exciting News: The Launch of the Aaron Gordon Signature Shoe, the AG 5",
            "https://x/blog.png",
            "https://www.361usa.com/blogs/news/the-ag-5",
        ),
        SearchHit("AG 5 BASKETBALL SHOES – 361sport", "https://x/coll.jpg", "https://361sport.com/collections/ag-5"),
        SearchHit("Untitled", "https://x/slug.png", "https://www.361usa.com/products/ag5-white"),
        SearchHit("AG 55 retro", "https://x/ag55.png", "https://x/products/ag-55"),
    ]
    matching, rejected = select_hits_for_name(hits, "AG 5")
    assert [h.link for h in matching] == [
        "https://x/slug.png",
        "https://x/coll.jpg",
        "https://x/blog.png",
    ]
    assert [r.link for r in rejected] == ["https://x/ag6.png", "https://x/ag55.png"]
    assert {r.why for r in rejected} == {"name_mismatch"}


def test_process_shoe_misses_when_no_hit_names_the_shoe(session, monkeypatch):
    from pipeline.images import search as search_mod

    row = _shoe(
        canonical_id="361-degrees-ag-5",
        brand="361 Degrees",
        name="AG 5",
        image_url="https://proj.supabase.co/storage/v1/object/public/shoe-images/stale-ag-6.png",
    )
    session.add(row)
    session.commit()
    monkeypatch.setattr(
        search_mod,
        "search_images",
        lambda *a, **k: [SearchHit("AG 6: AG Ion", "https://x/ag6.png")],
    )
    monkeypatch.setattr(
        search_mod,
        "choose_downloadable_image",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not download")),
    )

    with httpx.Client() as client:
        outcome = search_mod.process_shoe(
            session,
            client,
            row,
            search=SEARCH,
            supabase_url="https://proj.supabase.co",
            service_role_key="secret",
        )

    assert outcome == "missed"
    assert row.image_url is None
    assert row.extra_metadata["image_search"]["rejected"][0]["why"] == "name_mismatch"
