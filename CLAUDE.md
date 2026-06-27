# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Concert-With-Friends is a mobile app: enter favorite artists/genres, friend people you know, and get told which concerts are coming and which friends would want to go. It is a **closed friend-graph app** — no stranger matching by design (kills the cold-start problem).

Full build plan with schema and rationale is in `concert-buddy-build-plan.md`.

## Stack

- **Client:** React Native (Expo) — `mobile/`
- **Backend:** Python/FastAPI — `backend/`
- **Database:** PostgreSQL (SQLAlchemy async + asyncpg)
- **Job queue:** Celery + Redis
- **External APIs:** Ticketmaster Discovery API (events), Spotify API (artist similarity, Phase 4)

## Dev commands

**Start infrastructure (Postgres + Redis):**
```
docker-compose up -d
```

**Backend:**
```bash
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # then fill in SECRET_KEY
uvicorn app.main:app --reload                          # API at http://localhost:8000
```

**Run DB migrations:**
```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

**Celery worker + beat (event sync):**
```bash
cd backend
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info
```

**Manually trigger an event sync** (no Celery needed):
```
POST /admin/sync/{metro_id}   Header: X-Admin-Token: <SECRET_KEY>
```

**Mobile:**
```bash
cd mobile
npm install
npx expo start
```
Change `BASE_URL` in `mobile/src/api/client.ts` to your machine's LAN IP when testing on a physical device.

## Non-negotiables (architectural constraints)

- All matching/scoring happens **server-side**. The app is a thin view.
- **Token-based auth** (JWT or managed provider) with secure on-device token storage. No session cookies for a mobile client.
- **Cache Ticketmaster per-metro on a schedule**, never per-user on page load. Free tier: 5,000 calls/day, 5 req/sec. Watch the `Rate-Limit-Available` response header; back off at 429.
- Match on **metro/city, never raw coordinates**. Location precision is set once and enforced from the start.

## Build phases

1. **Phase 1 — Single-user feed:** Auth + artist/genre entry + scheduled event cache pull + personal nearby-show feed. Must be useful solo before friends join.
2. **Phase 2 — Social graph:** Mutual friend requests, unfriend/block, authz decisions on what each friend can see.
3. **Phase 3 — Matching:** Score friends per event (direct artist match > shared genre > in-metro > marked interest), surface "Band X is playing — Sam and Alex would probably go."
4. **Phase 4 — Taste similarity:** Resolve artists to Spotify IDs, pull related artists + genre tags, expand taste set so matching fires on adjacent artists (not just exact names). The interview-worthy subsystem.
5. **Phase 5 — Notification fan-out:** Nightly per-metro job, diff against cached events, enqueue notifications. Three hard constraints: idempotency (track `notifications_sent` to prevent double-notify), deduplication (one digest, not five pings), rate-sanity (stay under 5k/day).

## Schema decisions (costly to change later)

- **`artists` table** is keyed by `tm_attraction_id` (and later `spotify_id`). Resolving free-text names to canonical rows on entry prevents "Radiohead" vs "radiohead" duplication bugs.
- **`friendships` table** stores directional request + status. A unique index on `(LEAST(a,b), GREATEST(a,b))` enforces one row per unordered pair, preventing A→B and B→A both existing.
- **`notifications_sent`** is an idempotency ledger — `PRIMARY KEY (user_id, event_id)` — so the nightly job is safe to re-run.
- **`device_tokens`** must be refreshed on rotation; stale tokens silently kill push delivery.

## Ticketmaster Discovery API

Base URL: `https://app.ticketmaster.com/discovery/v2/` (pass `apikey=` on every call)

- Pull music events for a metro: `events.json?classificationName=music&dmaId={DMA}&apikey=...`
- Resolve artist name → attractionId: `attractions.json?keyword={name}&apikey=...`
- Events for a specific artist: `events.json?attractionId={id}&apikey=...`
