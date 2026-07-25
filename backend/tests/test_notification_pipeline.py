"""P4 notification pipeline (centerpiece 1) — grilled + locked 2026-07-25.

The failing-test matrix IS the spec (strict TDD, vertical slices):
  1. N new events for one user  -> exactly ONE digest covering all N
  2. run twice                  -> second run sends nothing (ledger idempotency)
  3. outbox recovery            -> send fails -> stays pending -> next run re-sends
  4. relevance bar              -> artist match sends, genre-only does not
  5. friend-mark ping           -> same-metro friends; private/cross-metro excluded
  6. mutual suppression         -> one touch per (recipient, event) across channels

Delivery goes through a Notifier seam so the pipeline is provable with no device;
P5 swaps in the real Expo push. Tests exercise the public service functions + a
fail-injectable fake, never the (future) push transport.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.models import Artist, Event, EventInterest, UserArtist, UserGenre
from app.services.notifications import Notification, notify_friend_mark, notify_new_events
from tests.conftest import befriend, create_user


class FakeNotifier:
    """Records what would be sent; can be told to fail (outbox-recovery slices)."""

    def __init__(self, fail: bool = False):
        self.sent: list[Notification] = []
        self.fail = fail

    async def send(self, notification: Notification) -> None:
        if self.fail:
            raise RuntimeError("push transport failed")
        self.sent.append(notification)


async def _add_favorite(db_session, user_id: str, name: str = "Turnstile", weight: int = 2) -> str:
    """Give a user an explicitly-picked artist; returns the artist id."""
    artist = Artist(tm_attraction_id=f"tm-{uuid.uuid4()}", name=name)
    db_session.add(artist)
    await db_session.flush()
    db_session.add(UserArtist(user_id=user_id, artist_id=artist.id, weight=weight))
    await db_session.commit()
    return artist.id


async def _event(db_session, artist_id: str | None, *, metro: str = "345",
                 name: str = "Show", days_ahead: int = 30) -> str:
    event = Event(
        tm_event_id=f"tm-{uuid.uuid4()}",
        name=name,
        artist_id=artist_id,
        metro_id=metro,
        starts_at=datetime.now(timezone.utc) + timedelta(days=days_ahead),
        venue_name="Venue",
    )
    db_session.add(event)
    await db_session.commit()
    return event.id


async def test_digest_collapses_a_users_new_events_into_one_notification(client, db_session):
    """N new relevant events for one user become ONE digest, not N pings."""
    user_id, _ = await create_user(client, "alice", metro="345")
    artist_id = await _add_favorite(db_session, user_id)
    e1 = await _event(db_session, artist_id, name="Show 1")
    e2 = await _event(db_session, artist_id, name="Show 2")

    notifier = FakeNotifier()
    await notify_new_events(db_session, [e1, e2], notifier)

    assert len(notifier.sent) == 1
    note = notifier.sent[0]
    assert note.user_id == user_id
    assert note.kind == "digest"
    assert set(note.event_ids) == {e1, e2}


async def test_running_twice_sends_nothing_the_second_time(client, db_session):
    """The `notifications_sent` ledger makes the pipeline idempotent — re-running
    the same new events delivers nothing the second time."""
    user_id, _ = await create_user(client, "alice", metro="345")
    artist_id = await _add_favorite(db_session, user_id)
    e1 = await _event(db_session, artist_id)

    notifier = FakeNotifier()
    await notify_new_events(db_session, [e1], notifier)
    await notify_new_events(db_session, [e1], notifier)

    assert len(notifier.sent) == 1


async def test_a_failed_send_is_retried_on_the_next_run(client, db_session):
    """Transactional outbox: a send that raises leaves the claim `pending` (nothing
    delivered, nothing lost) and a later run re-sends it. At-least-once, without ever
    holding a DB transaction across the push."""
    user_id, _ = await create_user(client, "alice", metro="345")
    artist_id = await _add_favorite(db_session, user_id)
    e1 = await _event(db_session, artist_id)

    failing = FakeNotifier(fail=True)
    await notify_new_events(db_session, [e1], failing)  # send raises internally
    assert failing.sent == []  # nothing delivered

    ok = FakeNotifier()
    await notify_new_events(db_session, [e1], ok)  # recovery re-send
    assert len(ok.sent) == 1
    assert set(ok.sent[0].event_ids) == {e1}


async def test_a_liked_artist_notifies_but_a_genre_only_match_does_not(client, db_session):
    """The digest bar is a direct artist pick (favorite OR liked tier) — deliberately
    tighter than the feed. A genre-only fan is NOT pushed; a picked artist is, even at
    the liked tier."""
    liker_id, _ = await create_user(client, "liker", metro="345")
    genre_fan_id, _ = await create_user(client, "genrefan", metro="345")

    # liker picks the event's artist at the *liked* tier (weight 1)
    artist_id = await _add_favorite(db_session, liker_id, name="Turnstile", weight=1)
    # genre_fan picks the Rock genre but not the artist
    db_session.add(UserGenre(user_id=genre_fan_id, genre="Rock"))
    await db_session.commit()

    e1 = await _event(db_session, artist_id, name="Turnstile @ 345")
    # tag the event's genre so a genre matcher *would* catch it if the bar were looser
    event = await db_session.get(Event, e1)
    event.genre = "Rock"
    await db_session.commit()

    notifier = FakeNotifier()
    await notify_new_events(db_session, [e1], notifier)

    recipients = {n.user_id for n in notifier.sent}
    assert recipients == {liker_id}  # genre_fan is NOT pushed


async def _mark(db_session, user_id: str, event_id: str, level="going", visibility="shared"):
    db_session.add(EventInterest(user_id=user_id, event_id=event_id, level=level, visibility=visibility))
    await db_session.commit()


async def test_friend_mark_pings_same_metro_friends_only(client, db_session):
    """A shared mark instantly pings the marker's friends IN THE EVENT'S METRO — no
    taste filter. Cross-metro friends are excluded (they see it in-app only)."""
    marker_id, marker_h = await create_user(client, "sam", metro="345")
    near_id, near_h = await create_user(client, "alex", metro="345")
    far_id, far_h = await create_user(client, "jordan", metro="999")
    await befriend(client, marker_h, marker_id, near_h, near_id)
    await befriend(client, marker_h, marker_id, far_h, far_id)

    artist_id = await _add_favorite(db_session, marker_id, name="Turnstile")
    e1 = await _event(db_session, artist_id, metro="345")
    await _mark(db_session, marker_id, e1, visibility="shared")

    notifier = FakeNotifier()
    await notify_friend_mark(db_session, marker_id, e1, notifier)

    recipients = {n.user_id for n in notifier.sent}
    assert recipients == {near_id}
    assert notifier.sent[0].kind == "friend_mark"


async def test_private_mark_fires_no_ping(client, db_session):
    """A PRIVATE mark never pings friends — it still feeds the marker's own feed, but
    stays invisible to everyone else."""
    marker_id, marker_h = await create_user(client, "sam", metro="345")
    near_id, near_h = await create_user(client, "alex", metro="345")
    await befriend(client, marker_h, marker_id, near_h, near_id)

    artist_id = await _add_favorite(db_session, marker_id, name="Turnstile")
    e1 = await _event(db_session, artist_id, metro="345")
    await _mark(db_session, marker_id, e1, visibility="private")

    notifier = FakeNotifier()
    await notify_friend_mark(db_session, marker_id, e1, notifier)

    assert notifier.sent == []


async def _setup_dual_trigger(client, db_session):
    """A recipient who BOTH matches the digest (picked the artist) AND has a same-metro
    friend marking the event shared — so both channels target the same (recipient, event)."""
    marker_id, marker_h = await create_user(client, "sam", metro="345")
    recip_id, recip_h = await create_user(client, "alex", metro="345")
    await befriend(client, marker_h, marker_id, recip_h, recip_id)
    artist_id = await _add_favorite(db_session, recip_id, name="Turnstile")
    e1 = await _event(db_session, artist_id, metro="345")
    await _mark(db_session, marker_id, e1, visibility="shared")
    return marker_id, recip_id, e1


async def test_digest_then_friend_mark_touches_recipient_once(client, db_session):
    marker_id, recip_id, e1 = await _setup_dual_trigger(client, db_session)
    notifier = FakeNotifier()
    await notify_new_events(db_session, [e1], notifier)        # digest claims first
    await notify_friend_mark(db_session, marker_id, e1, notifier)  # ping suppressed
    assert len([n for n in notifier.sent if n.user_id == recip_id]) == 1


async def test_friend_mark_then_digest_touches_recipient_once(client, db_session):
    marker_id, recip_id, e1 = await _setup_dual_trigger(client, db_session)
    notifier = FakeNotifier()
    await notify_friend_mark(db_session, marker_id, e1, notifier)  # ping claims first
    await notify_new_events(db_session, [e1], notifier)        # digest suppressed
    assert len([n for n in notifier.sent if n.user_id == recip_id]) == 1


async def test_empty_run_is_a_clean_no_op(db_session):
    """No new events → no sends, no crash."""
    notifier = FakeNotifier()
    await notify_new_events(db_session, [], notifier)
    assert notifier.sent == []
