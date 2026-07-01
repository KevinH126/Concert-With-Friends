"""Username rules: required at signup, validated, unique; legacy accounts set via PATCH."""
from tests.conftest import create_user


async def test_signup_returns_username_on_me(client):
    _, headers = await create_user(client, "kevin")
    me = await client.get("/auth/me", headers=headers)
    assert me.json()["username"] == "kevin"


async def test_signup_without_username_rejected(client):
    resp = await client.post(
        "/auth/signup",
        json={
            "email": "nouser@example.com",
            "display_name": "No User",
            "password": "password123",
        },
    )
    assert resp.status_code == 422


async def test_signup_username_taken(client):
    await create_user(client, "kevin")
    resp = await client.post(
        "/auth/signup",
        json={
            "email": "other@example.com",
            "username": "kevin",
            "display_name": "Other",
            "password": "password123",
        },
    )
    assert resp.status_code == 409


async def test_signup_invalid_usernames_rejected(client):
    for bad in ["ab", "Kevin", "has space", "has-dash", "x" * 21, "émile"]:
        resp = await client.post(
            "/auth/signup",
            json={
                "email": f"bad-{bad[:2]}@example.com",
                "username": bad,
                "display_name": "Bad",
                "password": "password123",
            },
        )
        assert resp.status_code == 422, f"{bad!r} should be rejected: {resp.text}"


async def test_patch_me_sets_username(client):
    _, headers = await create_user(client, "kevin")
    resp = await client.patch("/users/me", json={"username": "kevin_2"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "kevin_2"


async def test_patch_me_username_taken(client):
    await create_user(client, "kevin")
    _, headers_b = await create_user(client, "sam")
    resp = await client.patch("/users/me", json={"username": "kevin"}, headers=headers_b)
    assert resp.status_code == 409


async def test_patch_me_username_invalid(client):
    _, headers = await create_user(client, "kevin")
    resp = await client.patch("/users/me", json={"username": "Not Valid"}, headers=headers)
    assert resp.status_code == 422
