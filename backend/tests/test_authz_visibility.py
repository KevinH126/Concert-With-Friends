"""The authz matrix: friends-only taste + interest; private interest; feed strip; search."""
from app.models import Artist, UserArtist
from tests.conftest import befriend, create_user, give_genre, make_event


async def _add_artist(db_session, user_id: str, name: str, weight: int = 2):
    artist = Artist(name=name)
    db_session.add(artist)
    await db_session.flush()
    db_session.add(UserArtist(user_id=user_id, artist_id=artist.id, weight=weight))
    await db_session.commit()


# --- Profile access -------------------------------------------------------

async def test_non_friend_sees_nothing(client):
    id_a, _ = await create_user(client, "alice")
    _, hb = await create_user(client, "bob")
    resp = await client.get(f"/friends/{id_a}/profile", headers=hb)
    assert resp.status_code == 404


async def test_pending_sees_nothing(client):
    id_a, _ = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await client.post("/friends/requests", json={"user_id": id_a}, headers=hb)
    resp = await client.get(f"/friends/{id_a}/profile", headers=hb)
    assert resp.status_code == 404


async def test_friend_sees_taste(client, db_session):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await _add_artist(db_session, id_a, "Radiohead", weight=2)
    await give_genre(db_session, id_a, "Rock")
    await befriend(client, ha, id_a, hb, id_b)

    resp = await client.get(f"/friends/{id_a}/profile", headers=hb)
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["username"] == "alice"
    assert [(a["name"], a["weight"]) for a in profile["artists"]] == [("Radiohead", 2)]
    assert profile["genres"] == ["Rock"]


async def test_profile_never_exposes_email(client, db_session):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)
    profile = (await client.get(f"/friends/{id_a}/profile", headers=hb)).json()
    assert "email" not in profile


# --- Interest visibility --------------------------------------------------

async def test_friend_sees_shared_interest_not_private(client, db_session):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await befriend(client, ha, id_a, hb, id_b)

    shared_event = await make_event(db_session, name="Shared Show")
    private_event = await make_event(db_session, name="Private Show")
    await client.put(f"/feed/events/{shared_event}/interest",
                     json={"level": "going", "visibility": "shared"}, headers=ha)
    await client.put(f"/feed/events/{private_event}/interest",
                     json={"level": "going", "visibility": "private"}, headers=ha)

    profile = (await client.get(f"/friends/{id_a}/profile", headers=hb)).json()
    names = [i["event_name"] for i in profile["interests"]]
    assert "Shared Show" in names
    assert "Private Show" not in names


async def test_own_private_interest_still_in_own_feed(client, db_session):
    id_a, ha = await create_user(client, "alice")
    await give_genre(db_session, id_a, "Rock")
    event_id = await make_event(db_session, name="My Private Show")
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "going", "visibility": "private"}, headers=ha)

    feed = (await client.get("/feed", headers=ha)).json()
    mine = next(e for e in feed if e["id"] == event_id)
    assert mine["my_interest"] == "going"
    assert mine["my_interest_visibility"] == "private"


async def test_interest_default_visibility_is_shared(client, db_session):
    _, ha = await create_user(client, "alice")
    event_id = await make_event(db_session)
    resp = await client.put(f"/feed/events/{event_id}/interest",
                            json={"level": "maybe"}, headers=ha)
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "shared"


# --- Friends-going strip on the feed --------------------------------------

async def test_feed_strip_shows_friends_shared_interest_only(client, db_session):
    id_a, ha = await create_user(client, "alice")   # the viewer
    id_b, hb = await create_user(client, "bob")     # friend, shared
    id_c, hc = await create_user(client, "carol")   # friend, private
    _, hd = await create_user(client, "dave")       # NON-friend, shared

    await give_genre(db_session, id_a, "Rock")
    await befriend(client, ha, id_a, hb, id_b)
    await befriend(client, ha, id_a, hc, id_c)

    event_id = await make_event(db_session, name="The Big Show")
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "going", "visibility": "shared"}, headers=hb)
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "maybe", "visibility": "private"}, headers=hc)
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "going", "visibility": "shared"}, headers=hd)

    feed = (await client.get("/feed", headers=ha)).json()
    event = next(e for e in feed if e["id"] == event_id)
    going = {(g["user_id"], g["level"]) for g in event["friends_going"]}
    assert going == {(id_b, "going")}  # bob only: carol is private, dave is a stranger


async def test_switching_to_private_removes_from_strip(client, db_session):
    id_a, ha = await create_user(client, "alice")
    id_b, hb = await create_user(client, "bob")
    await give_genre(db_session, id_a, "Rock")
    await befriend(client, ha, id_a, hb, id_b)

    event_id = await make_event(db_session)
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "going", "visibility": "shared"}, headers=hb)
    await client.put(f"/feed/events/{event_id}/interest",
                     json={"level": "going", "visibility": "private"}, headers=hb)

    feed = (await client.get("/feed", headers=ha)).json()
    event = next(e for e in feed if e["id"] == event_id)
    assert event["friends_going"] == []


# --- Username search ------------------------------------------------------

async def test_search_min_length(client):
    _, ha = await create_user(client, "alice")
    resp = await client.get("/users/search", params={"q": "al"}, headers=ha)
    assert resp.status_code == 422


async def test_search_prefix_excludes_self_and_carries_status(client):
    id_a, ha = await create_user(client, "pal_alice")
    id_b, hb = await create_user(client, "pal_bob")      # will be friend
    id_c, _ = await create_user(client, "pal_carol")     # pending out
    id_d, hd = await create_user(client, "pal_dave")     # pending in
    await create_user(client, "pal_erin")                # none

    await befriend(client, ha, id_a, hb, id_b)
    await client.post("/friends/requests", json={"user_id": id_c}, headers=ha)
    await client.post("/friends/requests", json={"user_id": id_a}, headers=hd)

    results = (await client.get("/users/search", params={"q": "pal"}, headers=ha)).json()
    by_username = {r["username"]: r["friendship_status"] for r in results}
    assert "pal_alice" not in by_username  # self excluded
    assert by_username == {
        "pal_bob": "friends",
        "pal_carol": "pending_out",
        "pal_dave": "pending_in",
        "pal_erin": "none",
    }


async def test_search_matches_prefix_not_substring(client):
    _, ha = await create_user(client, "alice")
    await create_user(client, "bobcat")
    results = (await client.get("/users/search", params={"q": "cat"}, headers=ha)).json()
    assert results == []
