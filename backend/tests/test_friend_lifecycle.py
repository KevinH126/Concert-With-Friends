"""Friendship state machine: none -> pending -> accepted; decline/cancel/unfriend delete."""
from tests.conftest import befriend, create_user


async def test_request_then_accept(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")

    r = await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    assert r.status_code == 201

    reqs = (await client.get("/friends/requests", headers=hb)).json()
    assert [u["id"] for u in reqs["incoming"]] == [id_a]
    reqs_a = (await client.get("/friends/requests", headers=ha)).json()
    assert [u["id"] for u in reqs_a["outgoing"]] == [id_b]

    r = await client.post(f"/friends/requests/{id_a}/accept", headers=hb)
    assert r.status_code == 200

    friends_a = (await client.get("/friends", headers=ha)).json()
    friends_b = (await client.get("/friends", headers=hb)).json()
    assert [u["id"] for u in friends_a] == [id_b]
    assert [u["id"] for u in friends_b] == [id_a]


async def test_self_request_rejected(client):
    id_a, ha = await create_user(client, "alice")
    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=ha)
    assert r.status_code == 400


async def test_duplicate_request_rejected(client):
    _, ha = await create_user(client, "alice")
    id_b, _ = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    r = await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    assert r.status_code == 409


async def test_reverse_request_while_pending_rejected(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    assert r.status_code == 409


async def test_request_when_already_friends_rejected(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)
    r = await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)
    assert r.status_code == 409


async def test_request_unknown_user_404(client):
    _, ha = await create_user(client, "alice")
    r = await client.post(
        "/friends/requests",
        json={"user_id": "00000000-0000-0000-0000-000000000000"},
        headers=ha,
    )
    assert r.status_code == 404


async def test_decline_deletes_and_allows_rerequest(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)

    # bob declines alice's incoming request
    r = await client.request("DELETE", f"/friends/requests/{id_a}", headers=hb)
    assert r.status_code == 204
    assert (await client.get("/friends/requests", headers=hb)).json()["incoming"] == []

    # clean slate: alice can re-request, and even bob can request alice
    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    assert r.status_code == 201


async def test_cancel_outgoing_deletes(client):
    id_a, ha = await create_user(client, "alice")
    id_b, _ = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_b}, headers=ha)

    # alice cancels her own outgoing request
    r = await client.request("DELETE", f"/friends/requests/{id_b}", headers=ha)
    assert r.status_code == 204
    assert (await client.get("/friends/requests", headers=ha)).json()["outgoing"] == []


async def test_decline_nothing_pending_404(client):
    _, ha = await create_user(client, "alice")
    id_b, _ = await create_user(client, "bob")
    r = await client.request("DELETE", f"/friends/requests/{id_b}", headers=ha)
    assert r.status_code == 404


async def test_unfriend_deletes_and_allows_rerequest(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)

    r = await client.request("DELETE", f"/friends/{id_b}", headers=ha)
    assert r.status_code == 204
    assert (await client.get("/friends", headers=ha)).json() == []
    assert (await client.get("/friends", headers=hb)).json() == []

    r = await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    assert r.status_code == 201


async def test_unfriend_not_friends_404(client):
    _, ha = await create_user(client, "alice")
    id_b, _ = await create_user(client, "bob")
    r = await client.request("DELETE", f"/friends/{id_b}", headers=ha)
    assert r.status_code == 404


async def test_accept_without_pending_404(client):
    id_a, _ = await create_user(client, "alice")
    _, hb = await create_user(client, "bob")
    r = await client.post(f"/friends/requests/{id_a}/accept", headers=hb)
    assert r.status_code == 404
