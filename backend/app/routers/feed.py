from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, Event, EventInterest, User, UserArtist, UserGenre

router = APIRouter(prefix="/feed", tags=["feed"])


class EventResponse(BaseModel):
    id: str
    name: str
    artist_name: str | None
    venue_name: str | None
    starts_at: datetime | None
    genre: str | None
    my_interest: str | None  # 'going' | 'maybe' | None

    class Config:
        from_attributes = True


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

    # Collect this user's artist IDs and genres
    artist_rows = await db.execute(
        select(UserArtist.artist_id).where(UserArtist.user_id == current_user.id)
    )
    artist_ids = [r[0] for r in artist_rows.all()]

    genre_rows = await db.execute(
        select(UserGenre.genre).where(UserGenre.user_id == current_user.id)
    )
    genres = [r[0] for r in genre_rows.all()]

    now = datetime.now(timezone.utc)

    # Events in this metro that match artist OR genre, upcoming only
    filters = [Event.metro_id == current_user.home_metro_id, Event.starts_at >= now]
    match_clause = []
    if artist_ids:
        match_clause.append(Event.artist_id.in_(artist_ids))
    if genres:
        match_clause.append(Event.genre.in_(genres))

    if not match_clause:
        return []

    result = await db.execute(
        select(Event)
        .options(selectinload(Event.artist))
        .where(*filters, or_(*match_clause))
        .order_by(Event.starts_at)
    )
    events = result.scalars().all()

    # Fetch the user's interests for these event IDs
    event_ids = [e.id for e in events]
    interest_rows = await db.execute(
        select(EventInterest).where(
            EventInterest.user_id == current_user.id,
            EventInterest.event_id.in_(event_ids),
        )
    )
    interests = {i.event_id: i.level for i in interest_rows.scalars().all()}

    return [
        EventResponse(
            id=e.id,
            name=e.name,
            artist_name=e.artist.name if e.artist else None,
            venue_name=e.venue_name,
            starts_at=e.starts_at,
            genre=e.genre,
            my_interest=interests.get(e.id),
        )
        for e in events
    ]


class SetInterestRequest(BaseModel):
    level: str  # 'going' | 'maybe'


@router.put("/events/{event_id}/interest", response_model=dict)
async def set_interest(
    event_id: str,
    body: SetInterestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.level not in ("going", "maybe"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="level must be 'going' or 'maybe'")

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
    else:
        db.add(EventInterest(user_id=current_user.id, event_id=event_id, level=body.level))

    await db.commit()
    return {"event_id": event_id, "level": body.level}


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
