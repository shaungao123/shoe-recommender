"""Upsert writer unit tests — in-memory SQLite, no network, no Postgres."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pipeline.upsert.writer import shoe_values_from_canonical, upsert_shoes
from shared.db.models import Shoe


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    # only the shoes table — the embeddings Vector type is Postgres-only
    Shoe.__table__.create(engine)
    with Session(engine) as db:
        yield db


def make_canonical(**kwargs) -> dict:
    defaults = dict(
        canonical_id="nike-gt-cut-3",
        brand="Nike",
        model="G.T. Cut 3",
        version="3",
        msrp_usd_cents=19000,
        cushioning_tech="ZoomX",
        position_tags=["guard"],
        playstyle_tags=["slasher"],
        metrics={"runrepeat": {"overall": 88}, "weartesters": {"traction": 9}},
        pros=[{"source": "runrepeat", "text": "elite grip"}],
        cons=[],
        review_text=[],
        image_urls=["http://img/gt3-a.png", "http://img/gt3-b.png"],
        affiliate_url=None,
        provenance={"msrp_usd_cents": {"source": "runrepeat", "url": "http://rr/gt3"}},
        sources=[{"source": "runrepeat", "url": "http://rr/gt3", "fetched_at": "t"}],
    )
    defaults.update(kwargs)
    return defaults


# -- mapping -----------------------------------------------------------


def test_mapping_to_columns():
    values = shoe_values_from_canonical(make_canonical())
    assert values["canonical_id"] == "nike-gt-cut-3"
    assert values["brand"] == "Nike"
    assert values["name"] == "G.T. Cut 3"
    assert values["price"] == Decimal("190.00")
    assert values["currency"] == "USD"
    assert values["image_url"] == "http://img/gt3-a.png"
    assert values["affiliate_url"] is None
    assert values["source_url"] == "http://rr/gt3"
    assert values["specs"]["cushioning_tech"] == "ZoomX"
    assert values["specs"]["playstyle_tags"] == ["slasher"]
    # metrics stay keyed per source, never averaged
    assert values["extra_metadata"]["metrics"] == {
        "runrepeat": {"overall": 88},
        "weartesters": {"traction": 9},
    }
    assert values["extra_metadata"]["image_urls"] == [
        "http://img/gt3-a.png",
        "http://img/gt3-b.png",
    ]


def test_mapping_null_price_when_no_msrp():
    values = shoe_values_from_canonical(make_canonical(msrp_usd_cents=None))
    assert values["price"] is None


def test_mapping_handles_empty_containers():
    values = shoe_values_from_canonical(make_canonical(image_urls=[], sources=[]))
    assert values["image_url"] is None
    assert values["source_url"] is None


# -- upsert ------------------------------------------------------------


def test_insert(session):
    batch = [make_canonical(), make_canonical(canonical_id="jordan-40", model="Air Jordan 40")]
    result = upsert_shoes(session, batch)
    session.commit()

    assert (result.inserted, result.updated, result.deleted) == (2, 0, 0)
    assert set(session.scalars(select(Shoe.canonical_id))) == {"nike-gt-cut-3", "jordan-40"}


def test_rerun_is_idempotent(session):
    batch = [make_canonical()]
    upsert_shoes(session, batch)
    session.commit()

    result = upsert_shoes(session, batch)
    session.commit()

    assert (result.inserted, result.updated, result.deleted) == (0, 0, 0)
    assert session.scalars(select(Shoe)).one().price == Decimal("190.00")


def test_update_keeps_row_identity(session):
    upsert_shoes(session, [make_canonical()])
    session.commit()
    original_id = session.scalars(select(Shoe)).one().id

    result = upsert_shoes(session, [make_canonical(msrp_usd_cents=15900)])
    session.commit()

    row = session.scalars(select(Shoe)).one()
    assert (result.inserted, result.updated, result.deleted) == (0, 1, 0)
    assert row.id == original_id
    assert row.price == Decimal("159.00")


def test_shoe_without_msrp_is_written_with_null_price(session):
    result = upsert_shoes(session, [make_canonical(msrp_usd_cents=None)])
    session.commit()
    assert result.inserted == 1
    assert session.scalars(select(Shoe)).one().price is None


def test_rows_outside_batch_are_deleted(session):
    # a pre-pipeline mock row (no canonical_id) and a stale canonical row
    session.add(Shoe(brand="Mock", name="Mock Shoe", price=1, specs={}, extra_metadata={}))
    session.add(
        Shoe(canonical_id="retired-1", brand="Old", name="Retired", price=1, specs={}, extra_metadata={})
    )
    session.commit()

    result = upsert_shoes(session, [make_canonical()])
    session.commit()

    assert (result.inserted, result.deleted) == (1, 2)
    assert session.scalars(select(Shoe)).one().canonical_id == "nike-gt-cut-3"
