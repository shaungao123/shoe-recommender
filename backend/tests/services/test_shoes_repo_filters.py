"""Repository hard-filter tests for browse + recommend fallback pools."""

from decimal import Decimal

from app.db.repositories import shoes as shoes_repo
from tests.conftest import seed_shoe


def test_list_filtered_shoes_budget_max(db_session) -> None:
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

    rows = shoes_repo.list_filtered_shoes(db_session, budget_max=200)
    names = {r.name for r in rows}
    assert names == {"G.T. Cut 3", "LeBron 22"}


def test_list_filtered_shoes_null_budget_includes_all(db_session) -> None:
    seed_shoe(db_session, price=Decimal("90.00"))
    seed_shoe(
        db_session,
        canonical_id="pricey",
        name="Pricey",
        price=Decimal("300.00"),
    )
    rows = shoes_repo.list_filtered_shoes(db_session, budget_max=None)
    assert len(rows) == 2


def test_list_filtered_shoes_brand(db_session) -> None:
    seed_shoe(db_session)
    seed_shoe(
        db_session,
        canonical_id="jordan-40",
        brand="Jordan",
        name="Air Jordan 40",
        price=Decimal("200.00"),
    )
    rows = shoes_repo.list_filtered_shoes(db_session, brand="jordan")
    assert [r.brand for r in rows] == ["Jordan"]


def test_list_filtered_combined_and_overconstrained(db_session) -> None:
    seed_shoe(db_session)  # fair / slasher / low / standard / guard
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

    rows = shoes_repo.list_filtered_shoes(
        db_session,
        budget_max=150,
        outdoor="good",
        playstyle="slasher",
        cut="mid",
        width="wide",
        position="big",
    )
    assert [r.canonical_id for r in rows] == ["nike-giannis-immortality-4"]

    empty = shoes_repo.list_filtered_shoes(
        db_session,
        outdoor="good",
        cut="high",  # no shoe has high cut
    )
    assert empty == []
