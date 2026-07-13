"""API tests for GET /api/shoes and GET /api/shoes/{id}."""

from decimal import Decimal

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
    assert body["extra_metadata"]["image_urls"] == ["https://example.com/gt3.jpg"]
    assert body["extra_metadata"]["sources"][0]["source"] == "basketballshoespecs"
    assert body["playstyle_tags"] == ["slasher", "shooter"]
    assert body["width_fit"] == "standard"


def test_get_shoe_not_found(client):
    res = client.get("/api/shoes/999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Shoe not found"
