"""Multi-use invites: landing page, instant-accept redemption, cap/expiry/revoke."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.models import Invite
from tests.conftest import befriend, create_user


async def _create_invite(client, headers):
    resp = await client.post("/invites", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_invite_shape(client):
    _, ha = await create_user(client, "alice")
    invite = await _create_invite(client, ha)
    assert invite["token"]
    assert invite["max_uses"] == 25
    assert invite["url"].endswith(f"/invites/{invite['token']}")


async def test_landing_page_renders(client):
    _, ha = await create_user(client, "alice")
    invite = await _create_invite(client, ha)
    resp = await client.get(f"/invites/{invite['token']}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert invite["token"] in resp.text
    assert "Alice" in resp.text  # inviter display name


async def test_landing_page_unknown_token_404(client):
    resp = await client.get("/invites/doesnotexist")
    assert resp.status_code == 404


async def test_redeem_creates_instant_friendship(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    invite = await _create_invite(client, ha)

    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 200
    assert resp.json()["friend"]["id"] == id_a

    # No pending step: both sides see an accepted friendship immediately
    assert [u["id"] for u in (await client.get("/friends", headers=ha)).json()] == [id_b]
    assert [u["id"] for u in (await client.get("/friends", headers=hb)).json()] == [id_a]


async def test_redeem_is_multi_use(client):
    id_a, ha = await create_user(client, "alice")
    invite = await _create_invite(client, ha)
    for name in ["bob", "carol", "dave"]:
        _, h = await create_user(client, name)
        resp = await client.post(f"/invites/{invite['token']}/redeem", headers=h)
        assert resp.status_code == 200, resp.text
    assert len((await client.get("/friends", headers=ha)).json()) == 3


async def test_redeem_upgrades_pending_request(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)

    invite = await _create_invite(client, ha)
    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 200
    assert [u["id"] for u in (await client.get("/friends", headers=hb)).json()] == [id_a]


async def test_redeem_already_friends_idempotent(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)

    invite = await _create_invite(client, ha)
    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 200
    assert len((await client.get("/friends", headers=ha)).json()) == 1


async def test_self_redeem_400(client):
    _, ha = await create_user(client, "alice")
    invite = await _create_invite(client, ha)
    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=ha)
    assert resp.status_code == 400


async def test_redeem_unknown_token_404(client):
    _, ha = await create_user(client, "alice")
    resp = await client.post("/invites/doesnotexist/redeem", headers=ha)
    assert resp.status_code == 404


async def test_redeem_expired_410(client, db_session):
    _, ha = await create_user(client, "alice")
    _, hb = await create_user(client, "bob")
    invite = await _create_invite(client, ha)
    await db_session.execute(
        update(Invite)
        .where(Invite.token == invite["token"])
        .values(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    )
    await db_session.commit()

    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 410


async def test_redeem_revoked_410(client):
    _, ha = await create_user(client, "alice")
    _, hb = await create_user(client, "bob")
    invite = await _create_invite(client, ha)

    r = await client.request("DELETE", f"/invites/{invite['token']}", headers=ha)
    assert r.status_code == 204

    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 410


async def test_revoke_inviter_only(client):
    _, ha = await create_user(client, "alice")
    _, hb = await create_user(client, "bob")
    invite = await _create_invite(client, ha)
    r = await client.request("DELETE", f"/invites/{invite['token']}", headers=hb)
    assert r.status_code == 404


async def test_redeem_cap_reached_410(client, db_session):
    _, ha = await create_user(client, "alice")
    invite = await _create_invite(client, ha)
    await db_session.execute(
        update(Invite).where(Invite.token == invite["token"]).values(max_uses=1)
    )
    await db_session.commit()

    _, hb = await create_user(client, "bob")
    _, hc = await create_user(client, "carol")
    assert (await client.post(f"/invites/{invite['token']}/redeem", headers=hb)).status_code == 200
    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hc)
    assert resp.status_code == 410


async def test_blocked_pair_cannot_redeem(client):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    invite = await _create_invite(client, ha)
    await client.post(f"/friends/{id_b}/block", headers=ha)

    # The block wins over the invite, and the error is generic
    resp = await client.post(f"/invites/{invite['token']}/redeem", headers=hb)
    assert resp.status_code == 404
    assert (await client.get("/friends", headers=ha)).json() == []
