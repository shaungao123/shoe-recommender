from decimal import Decimal

from shared.db.models import Feedback, ProductEvent
from tests.conftest import seed_shoe


def test_submit_feedback_with_reasons_and_context(client, db_session):
    shoe = seed_shoe(db_session)
    response = client.post("/api/feedback", json={
        "session_id": "session-abcdefgh",
        "shoe_id": shoe.id,
        "vote": "down",
        "reasons": ["not_my_style", "too_expensive"],
        "comment": "Want a cleaner colorway.",
        "request_context": {"budget": 140, "position": "guard"},
    })
    assert response.status_code == 201
    row = db_session.get(Feedback, response.json()["id"])
    assert row.vote == "down"
    assert row.reasons == ["not_my_style", "too_expensive"]
    assert row.request_context["budget"] == 140


def test_feedback_validates_anonymous_session_and_reason(client):
    response = client.post("/api/feedback", json={"session_id": "short", "shoe_id": 1, "vote": "up"})
    assert response.status_code == 422
    response = client.post("/api/feedback", json={
        "session_id": "session-abcdefgh", "shoe_id": 1, "vote": "down", "reasons": ["bad"]
    })
    assert response.status_code == 422


def test_submit_anonymous_product_event(client, db_session):
    response = client.post("/api/events", json={
        "session_id": "session-abcdefgh",
        "event_name": "catalog_filtered",
        "properties": {"brand": "Nike", "result_count": 4},
    })
    assert response.status_code == 201
    row = db_session.get(ProductEvent, response.json()["id"])
    assert row.event_name == "catalog_filtered"
    assert row.properties["result_count"] == 4


def test_frontend_aliases_are_preserved(client, db_session):
    shoe = seed_shoe(db_session)
    feedback = client.post("/api/feedback", json={
        "session_id": "session-abcdefgh", "shoe_id": shoe.id, "vote": "down",
        "reason": "not_my_style", "request": {"aesthetic": "minimal"},
    })
    assert feedback.status_code == 201
    row = db_session.get(Feedback, feedback.json()["id"])
    assert row.reasons == ["not_my_style"]
    assert row.request_context == {"aesthetic": "minimal"}

    event = client.post("/api/events", json={
        "session_id": "session-abcdefgh", "name": "recommendation_viewed"
    })
    assert event.status_code == 201
    assert db_session.get(ProductEvent, event.json()["id"]).event_name == "recommendation_viewed"
