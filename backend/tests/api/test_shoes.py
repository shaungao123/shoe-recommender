"""API tests for GET /api/shoes and GET /api/shoes/{id}."""

from decimal import Decimal
from datetime import datetime, timezone

from tests.conftest import seed_shoe


def test_list_shoes_empty(client):
    res = client.get("/api/shoes")
    assert res.status_code == 200
    body = res.json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_shoes_returns_summaries(client, db_session):
    seed_shoe(db_session)
    seed_shoe(
        db_session,
        canonical_id="jordan-40",
        brand="Jordan",
        name="Air Jordan 40",
        price=Decimal("200.00"),
        specs={
            "cut_height": "mid",
            "width_fit": "standard",
            "outdoor_suitability": "bad",
            "playstyle_tags": ["all-around"],
            "position_tags": ["wing"],
            "release_year": 2025,
            "signature_player": "Michael Jordan",
            "weight_oz": 15.0,
            "cushioning_tech": "Formula 23 + Zoom Air",
        },
    )

    res = client.get("/api/shoes")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert [i["name"] for i in body["items"]] == ["G.T. Cut 3", "Air Jordan 40"]
    first = body["items"][0]
    assert first["brand"] == "Nike"
    assert first["price"] == 190.0
    assert first["playstyle_tags"] == ["slasher", "shooter"]
    assert first["position_tags"] == ["guard"]
    assert first["outdoor_suitability"] == "fair"
    assert first["cut_height"] == "low"
    assert first["width_fit"] == "standard"
    assert first["weight_oz"] == 12.5
    assert first["release_year"] == 2024
    assert first["cushioning_tech"] == "ZoomX"
    assert "specs" not in first
    assert "extra_metadata" not in first


def test_list_filter_brand(client, db_session):
    seed_shoe(db_session)
    seed_shoe(
        db_session,
        canonical_id="jordan-40",
        brand="Jordan",
        name="Air Jordan 40",
        price=Decimal("200.00"),
    )

    res = client.get("/api/shoes", params={"brand": "jordan"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["brand"] == "Jordan"


def test_list_filter_budget(client, db_session):
    seed_shoe(db_session, price=Decimal("120.00"))
    seed_shoe(
        db_session,
        canonical_id="nike-lebron-22",
        name="LeBron 22",
        price=Decimal("180.00"),
    )
    seed_shoe(
        db_session,
        canonical_id="jordan-40",
        brand="Jordan",
        name="Air Jordan 40",
        price=Decimal("220.00"),
    )

    res = client.get("/api/shoes", params={"budget_min": 150, "budget_max": 200})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "LeBron 22"


def test_list_filter_budget_min_gt_max_returns_422(client):
    res = client.get("/api/shoes", params={"budget_min": 200, "budget_max": 100})
    assert res.status_code == 422


def test_list_filter_outdoor_playstyle_cut_width_position(client, db_session):
    seed_shoe(db_session)  # fair / slasher / low / standard / guard
    seed_shoe(
        db_session,
        canonical_id="adidas-trae-young-3",
        brand="Adidas",
        name="Trae Young 3",
        price=Decimal("140.00"),
        specs={
            "cut_height": "low",
            "width_fit": "narrow",
            "outdoor_suitability": "good",
            "playstyle_tags": ["shooter"],
            "position_tags": ["guard"],
        },
    )
    seed_shoe(
        db_session,
        canonical_id="nike-giannis-immortality-4",
        name="Giannis Immortality 4",
        price=Decimal("90.00"),
        specs={
            "cut_height": "mid",
            "width_fit": "wide",
            "outdoor_suitability": "good",
            "playstyle_tags": ["slasher"],
            "position_tags": ["big"],
        },
    )

    res = client.get(
        "/api/shoes",
        params={
            "outdoor": "good",
            "playstyle": "slasher",
            "cut": "mid",
            "width": "wide",
            "position": "big",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["canonical_id"] == "nike-giannis-immortality-4"


def test_list_pagination(client, db_session):
    for i in range(5):
        seed_shoe(
            db_session,
            canonical_id=f"nike-shoe-{i}",
            name=f"Shoe {i}",
            price=Decimal(f"{100 + i}.00"),
        )

    res = client.get("/api/shoes", params={"limit": 2, "offset": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert len(body["items"]) == 2
    assert [i["name"] for i in body["items"]] == ["Shoe 2", "Shoe 3"]


def test_catalog_search_and_newest_sort(client, db_session):
    seed_shoe(db_session, name="Court Vision", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    seed_shoe(
        db_session,
        canonical_id="adidas-court-2026",
        brand="Adidas",
        name="Court Vision Pro",
        price=Decimal("150.00"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    res = client.get("/api/shoes", params={"search": "court", "sort": "newest"})
    assert res.status_code == 200
    assert [item["name"] for item in res.json()["items"]] == [
        "Court Vision Pro", "Court Vision"
    ]


def _catalog_names(client, **params):
    res = client.get("/api/shoes", params=params)
    assert res.status_code == 200
    return [item["name"] for item in res.json()["items"]]


def test_catalog_search_excludes_non_matches_and_ignores_punctuation(client, db_session):
    seed_shoe(db_session)  # Nike G.T. Cut 3
    seed_shoe(db_session, canonical_id="nike-sabrina-2", name="Sabrina 2")

    assert _catalog_names(client, search="sabrina") == ["Sabrina 2"]
    assert _catalog_names(client, search="gt cut") == ["G.T. Cut 3"]
    assert _catalog_names(client, search="nike sabrina") == ["Sabrina 2"]
    assert _catalog_names(client, search="100%") == []


def test_catalog_price_sorts_put_unpriced_shoes_last(client, db_session):
    seed_shoe(db_session, canonical_id="a", name="Unpriced", price=None)
    seed_shoe(db_session, canonical_id="b", name="Cheap", price=Decimal("90.00"))
    seed_shoe(db_session, canonical_id="c", name="Pricey", price=Decimal("200.00"))

    assert _catalog_names(client, sort="price_desc") == ["Pricey", "Cheap", "Unpriced"]
    assert _catalog_names(client, sort="price_asc") == ["Cheap", "Pricey", "Unpriced"]


def test_catalog_newest_uses_release_year_not_import_time(client, db_session):
    imported = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seed_shoe(db_session, canonical_id="a", name="Old", created_at=imported, specs={"release_year": 2019})
    seed_shoe(db_session, canonical_id="b", name="Unknown", created_at=imported, specs={"release_year": None})
    seed_shoe(db_session, canonical_id="c", name="New", created_at=imported, specs={"release_year": 2025})

    assert _catalog_names(client, sort="newest") == ["New", "Old", "Unknown"]


def _hoops_geek(**ratings):
    return {"metrics": {"thehoopsgeek": ratings}}


def test_catalog_returns_single_source_scores(client, db_session):
    seed_shoe(
        db_session,
        extra_metadata=_hoops_geek(overall=8.3, traction=9.0, outdoor="50%", expert_review_count=2),
    )
    seed_shoe(
        db_session,
        canonical_id="other",
        name="Lab Only",
        extra_metadata={"metrics": {"runrepeat": {"corescore": 90}}},
    )

    items = {i["name"]: i for i in client.get("/api/shoes").json()["items"]}

    scores = items["G.T. Cut 3"]["scores"]
    assert scores["source"] == "thehoopsgeek"
    assert (scores["overall"], scores["traction"], scores["outdoor_pct"]) == (8.3, 9.0, 50)
    assert items["Lab Only"]["scores"] is None


def test_catalog_score_sort_ranks_rated_shoes_first(client, db_session):
    seed_shoe(db_session, canonical_id="a", name="Unrated", extra_metadata={"metrics": {}})
    seed_shoe(db_session, canonical_id="b", name="Grippy", extra_metadata=_hoops_geek(traction=9.5, outdoor="9%"))
    seed_shoe(db_session, canonical_id="c", name="Tough", extra_metadata=_hoops_geek(traction=7.0, outdoor="80%"))

    assert _catalog_names(client, sort="score_traction") == ["Grippy", "Tough", "Unrated"]
    # Numeric, not text: "80%" must outrank "9%".
    assert _catalog_names(client, sort="score_outdoor") == ["Tough", "Grippy", "Unrated"]


def test_catalog_rejects_unknown_sort(client):
    res = client.get("/api/shoes", params={"sort": "popular"})
    assert res.status_code == 422


def test_get_shoe_detail_matches_db_shape(client, db_session):
    row = seed_shoe(db_session)

    res = client.get(f"/api/shoes/{row.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == row.id
    assert body["canonical_id"] == "nike-gt-cut-3"
    assert body["name"] == "G.T. Cut 3"
    assert body["affiliate_url"] is None
    assert body["source_url"].endswith("/nike-gt-cut-3/")
    # Typed specs keys from the live corpus
    assert body["specs"]["cushioning_tech"] == "ZoomX"
    assert body["specs"]["width_fit"] == "standard"
    assert body["specs"]["weight_oz"] == 12.5
    assert body["specs"]["playstyle_tags"] == ["slasher", "shooter"]
    # Typed extra_metadata from the live corpus
    assert body["extra_metadata"]["pros"][0]["text"] == "elite grip"
    assert body["extra_metadata"]["metrics"]["runrepeat"]["corescore"] == 90
    assert body["extra_metadata"].get("image_urls") in (None, [])
    assert body["extra_metadata"]["sources"][0]["source"] == "basketballshoespecs"
    assert body["playstyle_tags"] == ["slasher", "shooter"]
    assert body["width_fit"] == "standard"


def test_get_shoe_not_found(client):
    res = client.get("/api/shoes/999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Shoe not found"
