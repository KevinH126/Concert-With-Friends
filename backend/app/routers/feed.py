from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Event, EventInterest, User
from app.services import social
from app.services.matching import (
    EventFacts,
    ScoringCtx,
    assemble_taste_set,
    load_genre_parents,
    prediction_bucket,
    score,
)

router = APIRouter(prefix="/feed", tags=["feed"])


class FriendGoing(BaseModel):
    user_id: str
    display_name: str
    level: str  # 'going' | 'maybe'


class FriendPredicted(BaseModel):
    user_id: str
    display_name: str
    bucket: str  # 'probably' ("would probably go") | 'might' ("might be into this")


class EventResponse(BaseModel):
    id: str
    name: str
    artist_name: str | None
    venue_name: str | None
    starts_at: datetime | None
    genre: str | None
    url: str | None
    my_interest: str | None  # 'going' | 'maybe' | None
    my_interest_visibility: str | None  # 'shared' | 'private' | None
    # One strip, ordered marked-going > marked-maybe > predicted. No numeric scores
    # ever ride the API — the bucket is the only confidence signal.
    friends_going: list[FriendGoing] = []
    friends_predicted: list[FriendPredicted] = []

    class Config:
        from_attributes = True


def _event_facts(e: Event) -> EventFacts:
    return EventFacts(
        artist_id=e.artist_id,
        genre=e.genre,
        subgenre=e.subgenre,
        artist_popularity=(e.artist.tm_upcoming_events or 0) if e.artist else 0,
        starts_at=e.starts_at,
    )


@router.get("", response_model=list[EventResponse])
async def get_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.home_metro_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set your home metro before viewing the feed. PATCH /auth/me with home_metro_id.",
        )

    now = datetime.now(timezone.utc)

    # All upcoming events in the metro; inclusion is decided by score, not SQL —
    # the closed graph (a few hundred events) makes inline scoring trivial (pre-P4).
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.artist))
        .where(Event.metro_id == current_user.home_metro_id, Event.starts_at >= now)
    )
    events = result.scalars().all()
    event_ids = [e.id for e in events]

    my_taste = await assemble_taste_set(db, current_user.id, friend_visible=False)
    genre_parents = await load_genre_parents(db)

    # My interests for these events
    interest_rows = await db.execute(
        select(EventInterest).where(
            EventInterest.user_id == current_user.id,
            EventInterest.event_id.in_(event_ids),
        )
    )
    interests = {i.event_id: i for i in interest_rows.scalars().all()}

    # Friends' SHARED interest only — private never leaves its owner.
    friends_going: dict[str, list[FriendGoing]] = {}
    marked_by_event: dict[str, set[str]] = {}
    friend_id_list = await social.friend_ids(db, current_user.id)
    if friend_id_list and event_ids:
        rows = await db.execute(
            select(EventInterest, User)
            .join(User, User.id == EventInterest.user_id)
            .where(
                EventInterest.event_id.in_(event_ids),
                EventInterest.user_id.in_(friend_id_list),
                EventInterest.visibility == "shared",
            )
        )
        for interest, user in rows.all():
            friends_going.setdefault(interest.event_id, []).append(
                FriendGoing(user_id=user.id, display_name=user.display_name, level=interest.level)
            )
            marked_by_event.setdefault(interest.event_id, set()).add(user.id)

    # Friend predictions: each friend's FRIEND-VISIBLE taste (shared marks only —
    # the two-taste-set privacy rule), scored on taste alone (no social echo).
    friend_users: dict[str, User] = {}
    friend_tastes = {}
    if friend_id_list:
        user_rows = await db.execute(select(User).where(User.id.in_(friend_id_list)))
        friend_users = {u.id: u for u in user_rows.scalars().all()}
        for fid in friend_id_list:
            friend_tastes[fid] = await assemble_taste_set(db, fid, friend_visible=True)
    taste_only_ctx = ScoringCtx(
        now=now, genre_parents=genre_parents, friends_going=0, friends_maybe=0, own_interest=None
    )

    scored: list[tuple[float, Event]] = []
    predictions: dict[str, list[FriendPredicted]] = {}
    for e in events:
        facts = _event_facts(e)
        marked = marked_by_event.get(e.id, set())
        strip = friends_going.get(e.id, [])
        my_ctx = ScoringCtx(
            now=now,
            genre_parents=genre_parents,
            friends_going=sum(1 for f in strip if f.level == "going"),
            friends_maybe=sum(1 for f in strip if f.level == "maybe"),
            own_interest=interests[e.id].level if e.id in interests else None,
        )
        my_score = score(my_taste, facts, my_ctx)
        if my_score <= 0:
            continue  # inclusion = taste match OR friend interest OR own mark — all live in the score
        scored.append((my_score, e))

        for fid, f_taste in friend_tastes.items():
            if fid in marked:
                continue  # already on the strip as a real mark — never double-listed
            bucket = prediction_bucket(score(f_taste, facts, taste_only_ctx))
            if bucket is not None:
                predictions.setdefault(e.id, []).append(
                    FriendPredicted(
                        user_id=fid,
                        display_name=friend_users[fid].display_name,
                        bucket=bucket,
                    )
                )

    # Relevance order; ties (same score) break toward the sooner show.
    scored.sort(key=lambda pair: (-pair[0], pair[1].starts_at or now))

    def _strip_order(entry: FriendGoing) -> int:
        return 0 if entry.level == "going" else 1

    return [
        EventResponse(
            id=e.id,
            name=e.name,
            artist_name=e.artist.name if e.artist else None,
            venue_name=e.venue_name,
            starts_at=e.starts_at,
            genre=e.genre,
            url=e.url,
            my_interest=interests[e.id].level if e.id in interests else None,
            my_interest_visibility=interests[e.id].visibility if e.id in interests else None,
            friends_going=sorted(friends_going.get(e.id, []), key=_strip_order),
            friends_predicted=sorted(
                predictions.get(e.id, []), key=lambda p: 0 if p.bucket == "probably" else 1
            ),
        )
        for _, e in scored
    ]


class SetInterestRequest(BaseModel):
    level: str  # 'going' | 'maybe'
    # 'private' feeds your own feed/notifications but is invisible to friends.
    visibility: str = "shared"  # 'shared' | 'private'


@router.put("/events/{event_id}/interest", response_model=dict)
async def set_interest(
    event_id: str,
    body: SetInterestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.level not in ("going", "maybe"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="level must be 'going' or 'maybe'")
    if body.visibility not in ("shared", "private"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="visibility must be 'shared' or 'private'")

    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    result = await db.execute(
        select(EventInterest).where(
            EventInterest.user_id == current_user.id,
            EventInterest.event_id == event_id,
        )
    )
    interest = result.scalar_one_or_none()
    if interest:
        interest.level = body.level
        interest.visibility = body.visibility
    else:
        db.add(EventInterest(
            user_id=current_user.id,
            event_id=event_id,
            level=body.level,
            visibility=body.visibility,
        ))

    await db.commit()
    return {"event_id": event_id, "level": body.level, "visibility": body.visibility}


@router.delete("/events/{event_id}/interest", status_code=status.HTTP_204_NO_CONTENT)
async def remove_interest(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EventInterest).where(
            EventInterest.user_id == current_user.id,
            EventInterest.event_id == event_id,
        )
    )
    interest = result.scalar_one_or_none()
    if interest:
        await db.delete(interest)
        await db.commit()
