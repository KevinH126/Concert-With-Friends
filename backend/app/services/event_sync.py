"""
Pulls events from Ticketmaster for a given metro and upserts them into the DB.
Called by the Celery beat schedule (or triggered manually via the admin endpoint).
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal
from app.models import Artist, Event, TmGenre
from app.services.ticketmaster import fetch_events_for_metro, fetch_genre_taxonomy, parse_tm_event

logger = logging.getLogger(__name__)


async def sync_metro(metro_id: str, session_factory=None) -> int:
    """Fetch and upsert events for metro_id. Returns count of events processed.

    session_factory lets callers (e.g. the Celery worker) supply an engine bound
    to the current event loop; defaults to the app-wide AsyncSessionLocal.
    """
    factory = session_factory or AsyncSessionLocal
    raw_events = await fetch_events_for_metro(metro_id)
    logger.info("Fetched %d events for metro %s", len(raw_events), metro_id)

    async with factory() as db:
        count = 0
        for raw in raw_events:
            parsed = parse_tm_event(raw, metro_id)

            # Resolve or create the artist row so events actually link to artists
            artist_id = None
            tm_att_id = parsed.pop("tm_attraction_id", None)
            tm_att_name = parsed.pop("tm_attraction_name", None)
            tm_upcoming = parsed.pop("tm_upcoming_events", None)
            if tm_att_id:
                result = await db.execute(select(Artist).where(Artist.tm_attraction_id == tm_att_id))
                artist = result.scalar_one_or_none()
                if not artist:
                    artist = Artist(tm_attraction_id=tm_att_id, name=tm_att_name or parsed["name"])
                    db.add(artist)
                    await db.flush()
                if tm_upcoming is not None:
                    artist.tm_upcoming_events = tm_upcoming
                artist_id = artist.id

            # Upsert event (keyed by tm_event_id)
            stmt = (
                pg_insert(Event)
                .values(
                    tm_event_id=parsed["tm_event_id"],
                    name=parsed["name"],
                    artist_id=artist_id,
                    venue_name=parsed["venue_name"],
                    metro_id=parsed["metro_id"],
                    starts_at=parsed["starts_at"],
                    genre=parsed["genre"],
                    subgenre=parsed["subgenre"],
                    url=parsed["url"],
                )
                .on_conflict_do_update(
                    index_elements=["tm_event_id"],
                    set_={
                        "name": parsed["name"],
                        "artist_id": artist_id,
                        "venue_name": parsed["venue_name"],
                        "starts_at": parsed["starts_at"],
                        "genre": parsed["genre"],
                        "subgenre": parsed["subgenre"],
                        "url": parsed["url"],
                    },
                )
            )
            await db.execute(stmt)
            count += 1

        await db.commit()

    return count


async def sync_genres(session_factory=None) -> int:
    """Load TM's Music genre taxonomy into tm_genres (idempotent upsert).
    Fetched once in practice; safe to re-run. Returns rows processed."""
    factory = session_factory or AsyncSessionLocal
    rows = await fetch_genre_taxonomy()

    async with factory() as db:
        # Parents first so the self-referencing FK is always satisfiable.
        for row in sorted(rows, key=lambda r: r["parent_tm_id"] is not None):
            stmt = (
                pg_insert(TmGenre)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=["tm_id"],
                    set_={"name": row["name"], "parent_tm_id": row["parent_tm_id"]},
                )
            )
            await db.execute(stmt)
        await db.commit()

    logger.info("Synced %d TM genre taxonomy rows", len(rows))
    return len(rows)
