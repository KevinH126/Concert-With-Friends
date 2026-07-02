"""Event search over the cached metro events — never a live TM call (the artist
typeahead stays the only per-user TM call). Closes the "mark interest on any
show" gap: the API allowed it since P2, this gives the UI a path to find them.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, Event, EventInterest, User

router = APIRouter(prefix="/events", tags=["events"])

SEARCH_LIMIT = 50


class EventSearchResult(BaseModel):
    id: str
    name: str
    artist_name: str | None
    venue_name: str | None
    starts_at: datetime | None
    genre: str | None
    url: str | None
    my_interest: str | None  # 'going' | 'maybe' | None


@router.get("/search", response_model=list[EventSearchResult])
async def search_events(
    q: str = Query(min_length=2),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.home_metro_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set your home metro before searching. PATCH /auth/me with home_metro_id.",
        )

    pattern = f"%{q}%"
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.artist))
        .outerjoin(Artist, Artist.id == Event.artist_id)
        .where(
            Event.metro_id == current_user.home_metro_id,
            Event.starts_at >= datetime.now(timezone.utc),
            or_(
                Event.name.ilike(pattern),
                Event.venue_name.ilike(pattern),
                Artist.name.ilike(pattern),
            ),
        )
        .order_by(Event.starts_at)
        .limit(SEARCH_LIMIT)
    )
    events = result.scalars().all()

    interest_rows = await db.execute(
        select(EventInterest).where(
            EventInterest.user_id == current_user.id,
            EventInterest.event_id.in_([e.id for e in events]),
        )
    )
    interests = {i.event_id: i.level for i in interest_rows.scalars().all()}

    return [
        EventSearchResult(
            id=e.id,
            name=e.name,
            artist_name=e.artist.name if e.artist else None,
            venue_name=e.venue_name,
            starts_at=e.starts_at,
            genre=e.genre,
            url=e.url,
            my_interest=interests.get(e.id),
        )
        for e in events
    ]
