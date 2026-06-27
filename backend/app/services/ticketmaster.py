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


async def resolve_artist(name: str) -> tuple[str | None, str]:
    """
    Resolve a free-text artist name to (tm_attraction_id, canonical_name).
    Returns (None, name) if no API key is configured or no match found.
    """
    if not settings.ticketmaster_api_key:
        logger.warning("No Ticketmaster API key — using stub for artist '%s'", name)
        return None, name

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_BASE}/attractions.json",
            params={"keyword": name, "apikey": settings.ticketmaster_api_key, "size": 1},
        )
        _check_rate_limit(resp)
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

    events = []
    page = 0
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            resp = await client.get(
                f"{_BASE}/events.json",
                params={
                    "classificationName": "music",
                    "dmaId": metro_id,
                    "apikey": settings.ticketmaster_api_key,
                    "size": 200,
                    "page": page,
                    "sort": "date,asc",
                },
            )
            _check_rate_limit(resp)
            data = resp.json()
            batch = data.get("_embedded", {}).get("events", [])
            events.extend(batch)

            page_info = data.get("page", {})
            if page + 1 >= page_info.get("totalPages", 1):
                break
            page += 1

    return events


def parse_tm_event(raw: dict, metro_id: str) -> dict:
    """Normalize a raw Ticketmaster event dict into the shape our DB expects."""
    starts_at = None
    dates = raw.get("dates", {}).get("start", {})
    if dates.get("dateTime"):
        starts_at = dates["dateTime"]
    elif dates.get("localDate"):
        starts_at = dates["localDate"] + "T00:00:00Z"

    attractions = raw.get("_embedded", {}).get("attractions", [])
    tm_attraction_id = attractions[0]["id"] if attractions else None

    classifications = raw.get("classifications", [{}])
    genre = classifications[0].get("genre", {}).get("name") if classifications else None

    venue = raw.get("_embedded", {}).get("venues", [{}])[0]
    venue_name = venue.get("name")

    return {
        "tm_event_id": raw["id"],
        "name": raw["name"],
        "tm_attraction_id": tm_attraction_id,
        "venue_name": venue_name,
        "metro_id": metro_id,
        "starts_at": starts_at,
        "genre": genre,
    }


def _check_rate_limit(resp: httpx.Response) -> None:
    if resp.status_code == 429:
        raise RuntimeError("Ticketmaster rate limit hit (429)")
    resp.raise_for_status()


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
