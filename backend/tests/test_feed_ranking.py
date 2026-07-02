"""P3 ranked feed: relevance order, social pull-in, friend predictions,
and the privacy guarantees that survive all the way to the API surface."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models import Artist, Event, EventInterest, UserArtist
from tests.conftest import befriend, create_user, give_genre


async def make_artist_event(db_session, *, genre: str | None = None, subgenre: str | None = None,
                            metro: str = "345", days_ahead: int = 30,
                            popularity: int | None = None) -> tuple[str, str]:
    """Event with its own artist; returns (artist_id, event_id)."""
    artist = Artist(name=f"Band {uuid.uuid4().hex[:6]}", tm_upcoming_events=popularity)
    db_session.add(artist)
    await db_session.flush()
    event = Event(
        tm_event_id=f"tm-{uuid.uuid4()}",
        name=f"Show {uuid.uuid4().hex[:6]}",
        artist_id=artist.id,
        metro_id=metro,
        genre=genre,
        subgenre=subgenre,
        starts_at=datetime.now(timezone.utc) + timedelta(days=days_ahead),
        venue_name="Test Venue",
    )
    db_session.add(event)
    await db_session.commit()
    return artist.id, event.id


async def favorite_artist(db_session, user_id: str, artist_id: str, weight: int = 2):
    db_session.add(UserArtist(user_id=user_id, artist_id=artist_id, weight=weight))
    await db_session.commit()


async def mark(db_session, user_id: str, event_id: str, level: str = "going",
               visibility: str = "shared"):
    db_session.add(EventInterest(user_id=user_id, event_id=event_id,
                                 level=level, visibility=visibility))
    await db_session.commit()


class TestRankedOrder:
    async def test_favorite_artist_event_ranks_above_genre_match(self, client, db_session):
        user_id, headers = await create_user(client, "rankuser")
        await give_genre(db_session, user_id, "Rock")
        fav_artist, fav_event = await make_artist_event(db_session, days_ahead=80)
        _, genre_event = await make_artist_event(db_session, genre="Rock", days_ahead=7)
        await favorite_artist(db_session, user_id, fav_artist)

        resp = await client.get("/feed", headers=headers)
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        # Favorite months out still tops a genre match next week.
        assert ids.index(fav_event) < ids.index(genre_event)

    async def test_no_taste_no_friends_is_empty(self, client, db_session):
        _, headers = await create_user(client, "blankuser")
        await make_artist_event(db_session, genre="Rock")

        resp = await client.get("/feed", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestSocialPullIn:
    async def test_friend_shared_interest_pulls_in_non_matching_event(self, client, db_session):
        me, my_headers = await create_user(client, "pullme")
        friend, friend_headers = await create_user(client, "pullfriend")
        await befriend(client, my_headers, me, friend_headers, friend)
        _, event_id = await make_artist_event(db_session, genre="Country")  # not my taste
        await mark(db_session, friend, event_id, level="going", visibility="shared")

        resp = await client.get("/feed", headers=my_headers)
        events = {e["id"]: e for e in resp.json()}
        assert event_id in events
        strip = events[event_id]["friends_going"]
        assert [s["user_id"] for s in strip] == [friend]

    async def test_friend_private_interest_never_pulls_in(self, client, db_session):
        me, my_headers = await create_user(client, "privme")
        friend, friend_headers = await create_user(client, "privfriend")
        await befriend(client, my_headers, me, friend_headers, friend)
        _, event_id = await make_artist_event(db_session, genre="Country")
        await mark(db_session, friend, event_id, level="going", visibility="private")

        resp = await client.get("/feed", headers=my_headers)
        assert event_id not in {e["id"] for e in resp.json()}

    async def test_own_mark_keeps_non_matching_event_in_feed(self, client, db_session):
        me, my_headers = await create_user(client, "ownmark")
        _, event_id = await make_artist_event(db_session, genre="Country")
        await mark(db_session, me, event_id, level="going", visibility="private")

        resp = await client.get("/feed", headers=my_headers)
        events = {e["id"]: e for e in resp.json()}
        assert event_id in events
        assert events[event_id]["my_interest"] == "going"


class TestFriendPredictions:
    async def test_friend_with_favorite_artist_predicted_probably(self, client, db_session):
        me, my_headers = await create_user(client, "predme")
        friend, friend_headers = await create_user(client, "predfriend")
        await befriend(client, my_headers, me, friend_headers, friend)
        artist_id, event_id = await make_artist_event(db_session, genre="Rock")
        await give_genre(db_session, me, "Rock")            # I match, so I see the card
        await favorite_artist(db_session, friend, artist_id)  # friend loves the band

        resp = await client.get("/feed", headers=my_headers)
        events = {e["id"]: e for e in resp.json()}
        predicted = events[event_id]["friends_predicted"]
        assert predicted == [{"user_id": friend, "display_name": "Predfriend", "bucket": "probably"}]

    async def test_marked_friend_never_double_listed_as_predicted(self, client, db_session):
        me, my_headers = await create_user(client, "dblme")
        friend, friend_headers = await create_user(client, "dblfriend")
        await befriend(client, my_headers, me, friend_headers, friend)
        artist_id, event_id = await make_artist_event(db_session, genre="Rock")
        await give_genre(db_session, me, "Rock")
        await favorite_artist(db_session, friend, artist_id)
        await mark(db_session, friend, event_id, level="going", visibility="shared")

        resp = await client.get("/feed", headers=my_headers)
        events = {e["id"]: e for e in resp.json()}
        assert [s["user_id"] for s in events[event_id]["friends_going"]] == [friend]
        assert events[event_id]["friends_predicted"] == []

    async def test_private_history_never_leaks_into_predictions(self, client, db_session):
        """The two-taste-set rule, end to end: a friend's PRIVATE death-metal mark
        must not make the app predict them for other death-metal shows."""
        me, my_headers = await create_user(client, "leakme")
        friend, friend_headers = await create_user(client, "leakfriend")
        await befriend(client, my_headers, me, friend_headers, friend)
        await give_genre(db_session, me, "Death Metal")  # I see both cards

        _, secret_event = await make_artist_event(db_session, genre="Death Metal")
        await mark(db_session, friend, secret_event, level="going", visibility="private")
        _, other_event = await make_artist_event(db_session, genre="Death Metal")

        resp = await client.get("/feed", headers=my_headers)
        events = {e["id"]: e for e in resp.json()}
        assert events[other_event]["friends_predicted"] == []
        assert events[other_event]["friends_going"] == []
