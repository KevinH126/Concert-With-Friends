"""Block = silent full mutual severance; blocker-only unblock."""
from tests.conftest import befriend, create_user


async def test_block_severs_friendship(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)

    r = await client.post(f"/friends/{id_b}/block", headers=ha)
    assert r.status_code == 204

    assert (await client.get("/friends", headers=ha)).json() == []
    assert (await client.get("/friends", headers=hb)).json() == []


async def test_block_hides_from_search_both_directions(client):
    _, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post(f"/friends/{id_b}/block", headers=ha)

    res_a = (await client.get("/users/search", params={"q": "bob"}, headers=ha)).json()
    res_b = (await client.get("/users/search", params={"q": "ali"}, headers=hb)).json()
    assert res_a == []
    assert res_b == []


async def test_requests_between_blocked_fail_generically(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post(f"/friends/{id_b}/block", headers=ha)

    # Blocked user's request looks like the target doesn't exist — never reveals the block
    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    assert r.status_code == 404
    # And the blocker can't request the blockee either
    r = await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    assert r.status_code == 404


async def test_block_hides_profile_both_directions(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)
    await client.post(f"/friends/{id_b}/block", headers=ha)

    assert (await client.get(f"/friends/{id_b}/profile", headers=ha)).status_code == 404
    assert (await client.get(f"/friends/{id_a}/profile", headers=hb)).status_code == 404


async def test_block_overrides_pending_request(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)

    r = await client.post(f"/friends/{id_a}/block", headers=hb)
    assert r.status_code == 204
    assert (await client.get("/friends/requests", headers=ha)).json()["outgoing"] == []


async def test_only_blocker_can_unblock(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post(f"/friends/{id_b}/block", headers=ha)

    # bob (the blockee) cannot unblock
    r = await client.request("DELETE", f"/friends/{id_a}/block", headers=hb)
    assert r.status_code == 404

    # alice can, and the slate is clean: bob may request again
    r = await client.request("DELETE", f"/friends/{id_b}/block", headers=ha)
    assert r.status_code == 204
    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    assert r.status_code == 201


async def test_block_unknown_user_404(client):
    _, ha = await create_user(client, "alice")
    r = await client.post(
        "/friends/00000000-0000-0000-0000-000000000000/block", headers=ha
    )
    assert r.status_code == 404
