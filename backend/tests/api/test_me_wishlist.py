"""Profile and wishlist API tests — auth overridden for happy paths."""

from __future__ import annotations

from sqlalchemy import select

from app.dependencies import get_current_user
from shared.db.models import WishlistItem
from tests.conftest import seed_shoe, seed_user


def test_me_requires_auth(client):
    response = client.get("/api/me")
    assert response.status_code == 401


def test_wishlist_requires_auth(client):
    response = client.get("/api/wishlist")
    assert response.status_code == 401
    response = client.put("/api/wishlist/1")
    assert response.status_code == 401
    response = client.delete("/api/wishlist/1")
    assert response.status_code == 401


def test_get_and_patch_me(auth_client, auth_user):
    response = auth_client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(auth_user.id)
    assert body["email"] == auth_user.email
    assert body["display_name"] == "Player One"

    patched = auth_client.patch("/api/me", json={"display_name": "Court Runner"})
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Court Runner"

    cleared = auth_client.patch("/api/me", json={"display_name": "  "})
    assert cleared.status_code == 200
    assert cleared.json()["display_name"] is None


def test_wishlist_add_list_remove_idempotent(auth_client, auth_user, db_session):
    shoe = seed_shoe(db_session)
    other = seed_shoe(db_session, canonical_id="jordan-40", brand="Jordan", name="Jordan 40")

    first = auth_client.put(f"/api/wishlist/{shoe.id}")
    assert first.status_code == 200
    assert first.json()["shoe"]["id"] == shoe.id
    assert "saved_at" in first.json()

    again = auth_client.put(f"/api/wishlist/{shoe.id}")
    assert again.status_code == 200
    assert again.json()["shoe"]["id"] == shoe.id

    auth_client.put(f"/api/wishlist/{other.id}")
    listed = auth_client.get("/api/wishlist")
    assert listed.status_code == 200
    ids = [item["shoe"]["id"] for item in listed.json()["items"]]
    assert ids == [other.id, shoe.id]

    deleted = auth_client.delete(f"/api/wishlist/{shoe.id}")
    assert deleted.status_code == 204
    deleted_again = auth_client.delete(f"/api/wishlist/{shoe.id}")
    assert deleted_again.status_code == 204

    remaining = auth_client.get("/api/wishlist")
    assert [item["shoe"]["id"] for item in remaining.json()["items"]] == [other.id]


def test_wishlist_missing_shoe_returns_404(auth_client):
    response = auth_client.put("/api/wishlist/999999")
    assert response.status_code == 404


def test_wishlist_is_private_per_user(client, db_session):
    shoe = seed_shoe(db_session)
    user_a = seed_user(db_session, email="a@example.com", display_name="A")
    user_b = seed_user(db_session, email="b@example.com", display_name="B")

    app = client.app

    def as_user(user):
        app.dependency_overrides[get_current_user] = lambda: user

    as_user(user_a)
    assert client.put(f"/api/wishlist/{shoe.id}").status_code == 200
    assert len(client.get("/api/wishlist").json()["items"]) == 1

    as_user(user_b)
    assert client.get("/api/wishlist").json()["items"] == []
    assert client.put(f"/api/wishlist/{shoe.id}").status_code == 200
    assert len(client.get("/api/wishlist").json()["items"]) == 1

    as_user(user_a)
    assert len(client.get("/api/wishlist").json()["items"]) == 1

    app.dependency_overrides.pop(get_current_user, None)


def test_deleting_shoe_cascades_wishlist_row(auth_client, auth_user, db_session):
    shoe = seed_shoe(db_session)
    assert auth_client.put(f"/api/wishlist/{shoe.id}").status_code == 200

    db_session.delete(shoe)
    db_session.commit()

    rows = db_session.execute(
        select(WishlistItem).where(WishlistItem.user_id == auth_user.id)
    ).scalars().all()
    assert rows == []
    assert auth_client.get("/api/wishlist").json()["items"] == []


def test_deleting_user_cascades_wishlist_row(db_session):
    user = seed_user(db_session)
    shoe = seed_shoe(db_session)
    db_session.add(WishlistItem(user_id=user.id, shoe_id=shoe.id))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    rows = db_session.execute(select(WishlistItem)).scalars().all()
    assert rows == []
