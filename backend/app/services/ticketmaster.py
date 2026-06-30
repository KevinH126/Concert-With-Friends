"""
Ticketmaster Discovery API client.
When TICKETMASTER_API_KEY is empty, all calls return stubbed data so development
can proceed without an API key.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://app.ticketmaster.com/discovery/v2"
_RATE_LIMIT_DELAY = 0.2  # 5 req/sec safe floor
_PAGE_SIZE = 200
# Ticketmaster rejects deep pagination past this offset (size * page) with HTTP 400.
# We stop here; events are sorted date-asc so we keep the soonest shows. Full coverage
# of a >1000-event metro needs date-windowed queries — tracked for the P4 pipeline.
_MAX_RESULTS = 1000


async def resolve_artist(name: str) -> tuple[str | None, str]:
    """
    Resolve a free-text artist name to (tm_attraction_id, canonical_name).
    Returns (None, name) if no API key is configured or no match found.
    """
    if not settings.ticketmaster_api_key:
        logger.warning("No Ticketmaster API key — using stub for artist '%s'", name)
        return None, name

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await _get_with_backoff(
            client,
            f"{_BASE}/attractions.json",
            params={"keyword": name, "apikey": settings.ticketmaster_api_key, "size": 1},
        )
        data = resp.json()

    attractions = data.get("_embedded", {}).get("attractions", [])
    if not attractions:
        return None, name

    top = attractions[0]
    return top["id"], top["name"]


async def fetch_events_for_metro(metro_id: str) -> list[dict]:
    """
    Pull upcoming music events for a Ticketmaster DMA/market id.
    Returns a list of raw event dicts. Returns stub data if no API key.
    """
    if not settings.ticketmaster_api_key:
        logger.warning("No Ticketmaster API key — returning stub events for metro '%s'", metro_id)
        return _stub_events(metro_id)

    events: list[dict] = []
    page = 0
    hit_cap = False
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            try:
                resp = await _get_with_backoff(
                    client,
                    f"{_BASE}/events.json",
                    params={
                        "classificationName": "music",
                        "dmaId": metro_id,
                        "apikey": settings.ticketmaster_api_key,
                        "size": _PAGE_SIZE,
                        "page": page,
                        "sort": "date,asc",
                    },
                )
            except httpx.HTTPError as exc:
                # A bad/slow page (HTTP error, timeout, transport drop) shouldn't throw
                # away everything already fetched. If we have nothing yet, surface it.
                if events:
                    logger.warning(
                        "Ticketmaster request failed mid-sync for metro '%s' (%s); keeping "
                        "%d events fetched so far",
                        metro_id, type(exc).__name__, len(events),
                    )
                    break
                raise
            data = resp.json()
            batch = data.get("_embedded", {}).get("events", [])
            events.extend(batch)

            page_info = data.get("page", {})
            if page + 1 >= page_info.get("totalPages", 1):
                break
            page += 1
            if page * _PAGE_SIZE >= _MAX_RESULTS:
                hit_cap = True
                break

    if hit_cap:
        logger.warning(
            "Metro '%s' exceeds the Ticketmaster deep-paging cap (%d events); stored the "
            "soonest %d. Full coverage needs date-windowed queries (P4).",
            metro_id, _MAX_RESULTS, len(events),
        )
    return events


def _parse_dt(value: str | None) -> datetime | None:
    """Parse a Ticketmaster ISO-8601 timestamp into a tz-aware datetime."""
    if not value:
        return None
    # asyncpg requires a datetime object for timestamptz columns, not a string
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_tm_event(raw: dict, metro_id: str) -> dict:
    """Normalize a raw Ticketmaster event dict into the shape our DB expects."""
    starts_at = None
    dates = raw.get("dates", {}).get("start", {})
    if dates.get("dateTime"):
        starts_at = _parse_dt(dates["dateTime"])
    elif dates.get("localDate"):
        starts_at = _parse_dt(dates["localDate"] + "T00:00:00Z")

    attractions = raw.get("_embedded", {}).get("attractions", [])
    tm_attraction_id = attractions[0]["id"] if attractions else None
    tm_attraction_name = attractions[0].get("name") if attractions else None

    classifications = raw.get("classifications", [{}])
    genre = classifications[0].get("genre", {}).get("name") if classifications else None

    venue = raw.get("_embedded", {}).get("venues", [{}])[0]
    venue_name = venue.get("name")

    return {
        "tm_event_id": raw["id"],
        "name": raw["name"],
        "tm_attraction_id": tm_attraction_id,
        "tm_attraction_name": tm_attraction_name,
        "venue_name": venue_name,
        "metro_id": metro_id,
        "starts_at": starts_at,
        "genre": genre,
    }


async def _get_with_backoff(
    client: httpx.AsyncClient, url: str, params: dict, max_retries: int = 4
) -> httpx.Response:
    """GET that backs off on 429 instead of aborting the whole sync."""
    delay = 1.0
    for attempt in range(max_retries):
        resp = await client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        # Honor Retry-After when present, otherwise exponential backoff
        retry_after = resp.headers.get("Retry-After")
        wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
        logger.warning("Ticketmaster 429 — backing off %.1fs (attempt %d)", wait, attempt + 1)
        await asyncio.sleep(wait)
        delay *= 2
    raise RuntimeError("Ticketmaster rate limit hit (429) after retries")


def _stub_events(metro_id: str) -> list[dict]:
    return [
        {
            "id": "STUB_EVT_001",
            "name": "Radiohead Live",
            "dates": {"start": {"dateTime": "2026-08-15T20:00:00Z"}},
            "_embedded": {
                "attractions": [{"id": "STUB_ATT_RADIOHEAD", "name": "Radiohead"}],
                "venues": [{"name": "Stub Arena"}],
            },
            "classifications": [{"genre": {"name": "Rock"}}],
        },
        {
            "id": "STUB_EVT_002",
            "name": "Thom Yorke Solo",
            "dates": {"start": {"dateTime": "2026-09-01T19:30:00Z"}},
            "_embedded": {
                "attractions": [{"id": "STUB_ATT_THOM", "name": "Thom Yorke"}],
                "venues": [{"name": "Stub Theater"}],
            },
            "classifications": [{"genre": {"name": "Alternative"}}],
        },
        {
            "id": "STUB_EVT_003",
            "name": "Jazz Night",
            "dates": {"start": {"dateTime": "2026-07-20T21:00:00Z"}},
            "_embedded": {
                "attractions": [],
                "venues": [{"name": "Stub Jazz Club"}],
            },
            "classifications": [{"genre": {"name": "Jazz"}}],
        },
    ]
