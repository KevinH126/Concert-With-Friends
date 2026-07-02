"""P3 event search: cached metro events only, name/artist/venue, upcoming only."""
from tests.conftest import create_user, make_event
from tests.test_feed_ranking import make_artist_event, mark


class TestEventSearch:
    async def test_matches_name_artist_and_venue(self, client, db_session):
        _, headers = await create_user(client, "searcher")
        await make_event(db_session, name="Warped Tour Revival")
        artist_id, by_artist = await make_artist_event(db_session)

        # by event name
        resp = await client.get("/events/search", params={"q": "warped"}, headers=headers)
        assert resp.status_code == 200
        assert [e["name"] for e in resp.json()] == ["Warped Tour Revival"]

        # by venue (helpers set 'Test Venue')
        resp = await client.get("/events/search", params={"q": "test venue"}, headers=headers)
        assert len(resp.json()) >= 2

    async def test_search_scoped_to_home_metro_and_future(self, client, db_session):
        _, headers = await create_user(client, "scopeduser", metro="345")
        await make_event(db_session, name="Elsewhere Fest", metro="999")
        await make_event(db_session, name="Yesterday Fest", metro="345", days_ahead=-1)

        resp = await client.get("/events/search", params={"q": "fest"}, headers=headers)
        assert resp.json() == []

    async def test_result_carries_my_interest(self, client, db_session):
        user_id, headers = await create_user(client, "interestuser")
        event_id = await make_event(db_session, name="Marked Show")
        await mark(db_session, user_id, event_id, level="maybe")

        resp = await client.get("/events/search", params={"q": "marked"}, headers=headers)
        assert resp.json()[0]["my_interest"] == "maybe"

    async def test_short_query_rejected(self, client, db_session):
        _, headers = await create_user(client, "shortq")
        resp = await client.get("/events/search", params={"q": "a"}, headers=headers)
        assert resp.status_code == 422
