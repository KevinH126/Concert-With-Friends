"""Taste-set assembler — builds the scorer's TasteSet from the DB.

Pins the two-variant privacy rule: friend-visible taste never includes
private marks; your own feed's taste includes everything.
"""
import uuid

from app.models import Artist, Event, EventInterest, User, UserArtist, UserGenre
from app.services.matching import assemble_taste_set


async def make_user(db_session) -> str:
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        username=f"u{uuid.uuid4().hex[:12]}",
        display_name="Test User",
        hashed_password="x",
        home_metro_id="345",
    )
    db_session.add(user)
    await db_session.commit()
    return user.id


async def make_artist(db_session) -> str:
    artist = Artist(name=f"Band {uuid.uuid4().hex[:6]}")
    db_session.add(artist)
    await db_session.commit()
    return artist.id


class TestExplicitPicks:
    async def test_weight_tiers_map_to_favorite_and_liked(self, db_session):
        user_id = await make_user(db_session)
        fav, liked = await make_artist(db_session), await make_artist(db_session)
        db_session.add(UserArtist(user_id=user_id, artist_id=fav, weight=2))
        db_session.add(UserArtist(user_id=user_id, artist_id=liked, weight=1))
        db_session.add(UserGenre(user_id=user_id, genre="Rock"))
        await db_session.commit()

        taste = await assemble_taste_set(db_session, user_id, friend_visible=False)

        assert taste.favorite_artist_ids == frozenset({fav})
        assert taste.liked_artist_ids == frozenset({liked})
        assert taste.genres == frozenset({"Rock"})


async def make_marked_event(db_session, user_id: str, *, level: str,
                            visibility: str = "shared", genre: str = "Hardcore") -> str:
    """Create an event with its own artist and mark it for the user; returns artist_id."""
    artist_id = await make_artist(db_session)
    event = Event(
        tm_event_id=f"tm-{uuid.uuid4()}",
        name="Marked Show",
        artist_id=artist_id,
        metro_id="345",
        genre=genre,
    )
    db_session.add(event)
    await db_session.flush()
    db_session.add(EventInterest(
        user_id=user_id, event_id=event.id, level=level, visibility=visibility,
    ))
    await db_session.commit()
    return artist_id


class TestInterestHistory:
    async def test_marks_feed_history_tiers_with_artist_and_genre(self, db_session):
        user_id = await make_user(db_session)
        going_artist = await make_marked_event(db_session, user_id, level="going", genre="Hardcore")
        maybe_artist = await make_marked_event(db_session, user_id, level="maybe", genre="Shoegaze")

        taste = await assemble_taste_set(db_session, user_id, friend_visible=False)

        assert taste.history_going_artist_ids == frozenset({going_artist})
        assert taste.history_maybe_artist_ids == frozenset({maybe_artist})
        assert taste.history_genres == frozenset({"Hardcore", "Shoegaze"})
        # History never pollutes the explicit tiers.
        assert taste.favorite_artist_ids == frozenset()
        assert taste.liked_artist_ids == frozenset()


class TestPrivacyVariants:
    """Locked rule: private marks never feed friend-visible results — not even
    as a hidden scorer input. Your own feed still learns from them."""

    async def test_friend_visible_taste_excludes_private_marks(self, db_session):
        user_id = await make_user(db_session)
        secret_artist = await make_marked_event(
            db_session, user_id, level="going", visibility="private", genre="Death Metal"
        )

        friend_view = await assemble_taste_set(db_session, user_id, friend_visible=True)

        assert secret_artist not in friend_view.history_going_artist_ids
        assert "Death Metal" not in friend_view.history_genres

    async def test_own_taste_includes_private_marks(self, db_session):
        user_id = await make_user(db_session)
        secret_artist = await make_marked_event(
            db_session, user_id, level="going", visibility="private", genre="Death Metal"
        )

        own_view = await assemble_taste_set(db_session, user_id, friend_visible=False)

        assert secret_artist in own_view.history_going_artist_ids
        assert "Death Metal" in own_view.history_genres

    async def test_shared_marks_feed_both_variants(self, db_session):
        user_id = await make_user(db_session)
        artist = await make_marked_event(db_session, user_id, level="going", visibility="shared")

        friend_view = await assemble_taste_set(db_session, user_id, friend_visible=True)
        own_view = await assemble_taste_set(db_session, user_id, friend_visible=False)

        assert artist in friend_view.history_going_artist_ids
        assert artist in own_view.history_going_artist_ids
