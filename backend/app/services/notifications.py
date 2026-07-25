"""P4 notification pipeline (centerpiece 1) — grilled + locked 2026-07-25.

Computes and delivers notifications through a `Notifier` seam so the whole pipeline
is provable with no device; P5 swaps in the real Expo push with zero changes here.
See the P4 section of docs/concert-buddy-build-plan.md for the locked design
(transactional outbox, artist-match-only digest bar, ledger dedup across channels).
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import Event, EventInterest, Friendship, NotificationSent, User, UserArtist

logger = logging.getLogger(__name__)


class Notification:
    """One delivered push. `event_ids` is what it covers — the ledger grain."""

    def __init__(self, user_id: str, kind: str, event_ids: list[str]):
        self.user_id = user_id
        self.kind = kind
        self.event_ids = event_ids


class Notifier(Protocol):
    async def send(self, notification: Notification) -> None: ...


class LogNotifier:
    """P4's real delivery until P5 wires Expo push — records each notification to the
    log so the pipeline runs end-to-end in prod with no device. Swapping in the Expo
    PushNotifier at P5 touches nothing else."""

    async def send(self, notification: Notification) -> None:
        logger.info(
            "NOTIFY user=%s kind=%s events=%d %s",
            notification.user_id, notification.kind,
            len(notification.event_ids), notification.event_ids,
        )


async def _digest_matches(db: AsyncSession, event_ids: list[str]) -> dict[str, list[str]]:
    """Map user_id -> the event_ids they match, at the digest relevance bar:
    the user explicitly picked the event's artist AND lives in the event's metro.
    Deliberately tighter than the feed — a push says "an artist you named is playing."
    """
    events = (await db.execute(select(Event).where(Event.id.in_(event_ids)))).scalars().all()
    per_user: dict[str, list[str]] = defaultdict(list)
    for event in events:
        if event.artist_id is None:
            continue
        rows = await db.execute(
            select(UserArtist.user_id)
            .join(User, User.id == UserArtist.user_id)
            .where(
                UserArtist.artist_id == event.artist_id,
                User.home_metro_id == event.metro_id,
            )
        )
        for (user_id,) in rows.all():
            per_user[user_id].append(event.id)
    return per_user


async def _claim_rows(db: AsyncSession, rows: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Claim (user, event) ledger rows as 'pending' and commit immediately — no
    transaction is held across the later push. `ON CONFLICT DO NOTHING` is the
    idempotency point AND the cross-channel dedup: a row already claimed by the other
    trigger (digest ↔ friend-mark) is left untouched. Returns the rows NEWLY claimed."""
    if not rows:
        return set()
    stmt = (
        pg_insert(NotificationSent)
        .values([{"user_id": u, "event_id": e, "status": "pending"} for u, e in rows])
        .on_conflict_do_nothing(index_elements=["user_id", "event_id"])
        .returning(NotificationSent.user_id, NotificationSent.event_id)
    )
    result = await db.execute(stmt)
    newly = {(row[0], row[1]) for row in result.all()}
    await db.commit()
    return newly


async def _mark_sent(db: AsyncSession, user_id: str, event_ids: list[str]) -> None:
    await db.execute(
        update(NotificationSent)
        .where(NotificationSent.user_id == user_id, NotificationSent.event_id.in_(event_ids))
        .values(status="sent", sent_at=func.now())
    )
    await db.commit()


async def _flush_pending(db: AsyncSession, user_id: str, notifier: Notifier) -> None:
    """Deliver everything still 'pending' for a user as one digest, then mark it 'sent'.
    Picks up both freshly-claimed events and any stuck from a prior failed run (the
    recovery path). A send failure leaves the rows 'pending' for the next run to retry."""
    rows = await db.execute(
        select(NotificationSent.event_id).where(
            NotificationSent.user_id == user_id,
            NotificationSent.status == "pending",
        )
    )
    pending = [row[0] for row in rows.all()]
    if not pending:
        return
    try:
        await notifier.send(Notification(user_id=user_id, kind="digest", event_ids=pending))
    except Exception:  # noqa: BLE001 — any delivery failure: leave pending, retry next run
        logger.warning("Digest send failed for user %s; %d events left pending", user_id, len(pending))
        return
    await _mark_sent(db, user_id, pending)


async def notify_new_events(db: AsyncSession, event_ids: list[str], notifier: Notifier) -> None:
    """Digest path: claim each user's matched new events as pending, then flush.
    Idempotent (ledger) and at-least-once (outbox recovery of stuck-pending rows)."""
    per_user = await _digest_matches(db, event_ids)
    for user_id, matched in per_user.items():
        await _claim_rows(db, [(user_id, e) for e in matched])
    for user_id in per_user:
        await _flush_pending(db, user_id, notifier)


async def _friends_in_metro(db: AsyncSession, user_id: str, metro_id: str | None) -> list[str]:
    """Accepted friends of user_id whose home metro is metro_id. Cross-metro friends
    are intentionally excluded — they see a shared mark in-app (feed strip) only."""
    if metro_id is None:
        return []
    rows = await db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    )
    friend_ids = [addr if req == user_id else req for req, addr in rows.all()]
    if not friend_ids:
        return []
    in_metro = await db.execute(
        select(User.id).where(User.id.in_(friend_ids), User.home_metro_id == metro_id)
    )
    return [row[0] for row in in_metro.all()]


async def notify_friend_mark(db: AsyncSession, marker_id: str, event_id: str, notifier: Notifier) -> None:
    """Friend-mark ping: a SHARED going/maybe instantly pings the marker's same-metro
    friends (no taste filter). Deduped via the shared ledger so each recipient gets at
    most one push per event across both channels; a private mark fires nothing."""
    interest = await db.get(EventInterest, (marker_id, event_id))
    if interest is None or interest.visibility != "shared":
        return
    event = await db.get(Event, event_id)
    if event is None:
        return
    friends = await _friends_in_metro(db, marker_id, event.metro_id)
    newly = await _claim_rows(db, [(friend_id, event_id) for friend_id in friends])
    for friend_id, _event_id in newly:
        try:
            await notifier.send(Notification(user_id=friend_id, kind="friend_mark", event_ids=[event_id]))
        except Exception:  # noqa: BLE001 — leave pending, recovered on a later run
            logger.warning("Friend-mark ping failed for user %s event %s; left pending", friend_id, event_id)
            continue
        await _mark_sent(db, friend_id, [event_id])


async def flush_all_pending(db: AsyncSession, notifier: Notifier) -> None:
    """Recovery sweep: re-deliver every user's stuck-'pending' rows. Catches rows
    orphaned by a failed send whose user has no new events in the current run (the
    per-user digest path would otherwise never revisit them). Run after the nightly
    fan-out and/or on its own periodic schedule."""
    rows = await db.execute(
        select(NotificationSent.user_id).where(NotificationSent.status == "pending").distinct()
    )
    for (user_id,) in rows.all():
        await _flush_pending(db, user_id, notifier)


async def run_metro_pipeline(
    db: AsyncSession,
    metro_id: str,
    notifier: Notifier,
    *,
    sync: Callable[[str], Awaitable[object]],
) -> None:
    """One metro's nightly run: snapshot the cache, sync, then digest only the events
    that are NEW this run (new = fetched − snapshot). `sync` is injected so the diff is
    the unit under test; prod passes the real per-metro Ticketmaster sync."""
    before = {
        row[0]
        for row in (
            await db.execute(select(Event.tm_event_id).where(Event.metro_id == metro_id))
        ).all()
    }
    await sync(metro_id)
    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(Event.id, Event.tm_event_id, Event.starts_at).where(Event.metro_id == metro_id)
    )
    new_event_ids = [
        event_id
        for event_id, tm_event_id, starts_at in rows.all()
        if tm_event_id not in before and (starts_at is None or starts_at > now)
    ]
    await notify_new_events(db, new_event_ids, notifier)
