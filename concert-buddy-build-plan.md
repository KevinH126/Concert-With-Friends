# Concert-With-Friends — Build Plan

A mobile app where you enter your favorite artists/genres, friend people you already
know, and get told **which concerts are coming and which of your friends would actually
want to go with you.**

## Scoping decision (read this first)

Build the **closed friend-graph** version, for a real friend group (yours), and do not
try to support strangers. This is deliberate, not a compromise:

- It kills the cold-start problem that sank every competitor (Radiate, Beatmatch, etc.).
  A stranger-matching app is useless until thousands of locals join; a friends-only app
  is useful the moment your ten friends join, because the trust already exists.
- It is a cleaner system to design and gives you a working demo with **real data**.
- Phases 1–3 below are a complete, demoable portfolio piece on their own.
  Phases 4–5 are the "depth" upgrades — do them *after* the core works end to end.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Client | React Native (Expo) — `mobile/` | Expo wraps APNs + FCM behind one push API |
| Backend | Python/FastAPI — `backend/` | Async-first; fast to build |
| Database | **PostgreSQL** (SQLAlchemy async + asyncpg) | Domain is all relationships → join tables + FKs |
| Job queue | Celery + Redis | For the notification fan-out in Phase 5 |
| External data | Ticketmaster Discovery API (events), Spotify API (artist similarity, Phase 4) | Free tiers cover a personal project |

**Non-negotiables (architectural constraints):**
- All matching/scoring happens **server-side**. The app is a thin view. Keeps taste
  models and friends' data off the device and keeps the authz story clean.
- Token-based auth (JWT or a managed provider) with secure on-device token storage.
  Do not use session cookies for a mobile client.
- **Cache Ticketmaster per-metro on a schedule**, never per-user on page load. Watch the
  `Rate-Limit-Available` response header; back off at 429.
- Match on **metro/city, never raw coordinates.** Location precision is set once and
  enforced from the start.

**API limits to design around:**
- Ticketmaster free tier: **5,000 calls/day, 5 req/sec.** Cache aggressively, pull
  **per-metro on a schedule**, never per-user on page load.

---

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

---

## Phases & milestones

### Phase 1 — Single-user "my shows" *(the foundation; ~1–2 weekends)*
No social features yet. Sign up → enter artists/genres → see nearby concerts.
This forces auth, DB, the third-party API, and caching into place.

- [ ] Auth (signup/login, token issuance, secure storage on device)
- [ ] Enter favorite artists → **resolve each to a canonical artist row** (see schema note)
- [ ] Enter favorite genres (from API classifications)
- [ ] Scheduled job pulls events per metro from Ticketmaster into the `events` cache
- [ ] Feed: upcoming nearby events matching the user's artists/genres
- **Done when:** the app is genuinely useful *solo* — a clean nearby-concerts feed for
  your own taste. This solves the empty-state problem before the social graph fills in.

### Phase 2 — The social graph *(~1 weekend)*
- [ ] Friend requests with mutual consent (request → accept/decline)
- [ ] Unfriend, and block
- [ ] **Authz decisions, made explicitly:** who can see your favorite artists, who can
  see that you're interested in a show, what location precision is exposed
  (match on **metro/city, never raw coordinates** — decide and enforce now)
- **Done when:** two real accounts can become friends and see each other's
  (permitted) taste.

### Phase 3 — Matching *(the heart; ~1 weekend)*
For an upcoming event, score each friend on how likely they'd want to go.

- [ ] Score = weighted sum of: direct artist match (strongest) + shared-genre count +
      in-range (metro) + already-marked-interest (near-certainty)
- [ ] Rank **friends per event**
- [ ] Feed headline becomes: *"Band X is playing nearby — Sam and Alex would probably
      go with you."*
- **Done when:** the app tells you *who* to go with, not just *what's* playing.
  Start dead simple and explainable; improve later.

### Phase 4 — Taste similarity *(the depth; the bigger time sink)*
String-matching artists makes the app feel dead — it only fires on exact names.

- [ ] Resolve each liked artist to a Spotify ID
- [ ] Pull **related artists** + genre tags, store an expanded "taste set" per user
- [ ] Matching now lights up on adjacent artists (likes Radiohead → Thom Yorke, etc.)
- **Stop here unless you want more:** related-artists gets ~80% of the magic. Embeddings
  from co-occurrence are a stretch goal, not a requirement.
- **This is the subsystem worth talking about in an interview.**

### Phase 5 — Notification fan-out *(the systems work; the other time sink)*
A scheduled background job, not request-driven.

- [ ] Nightly per-metro: pull new events, **diff against already-cached** events
- [ ] For each genuinely-new relevant event, compute matches and enqueue notifications
- [ ] **Idempotency:** running the job twice must not double-notify (track sent-per-user-
      per-event)
- [ ] **Deduplication:** one digest, not five pings for five bands the same night
- [ ] **Rate-sanity:** per-metro pulls, aggressive caching, stay under 5k/day
- **"I built an idempotent notification pipeline" is a sentence that lands.**

---

## Schema (the parts annoying to change later)

```sql
-- Identity
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    home_metro_id   TEXT,                  -- Ticketmaster DMA/market id
    location_precision TEXT NOT NULL DEFAULT 'metro'
                      CHECK (location_precision IN ('metro','city')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Canonical artists. Key by external id so you dedupe instead of free-texting names.
-- This one decision saves you from "Radiohead" vs "radiohead" vs "Radio Head" hell.
CREATE TABLE artists (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_attraction_id TEXT UNIQUE,          -- Ticketmaster attractionId
    spotify_id      TEXT UNIQUE,           -- filled in Phase 4
    name            TEXT NOT NULL
);

-- Who likes whom, with an optional weight (favorite vs mild).
CREATE TABLE user_artists (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    artist_id  UUID REFERENCES artists(id) ON DELETE CASCADE,
    weight     SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, artist_id)
);

CREATE TABLE user_genres (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    genre      TEXT NOT NULL,              -- from API classification
    PRIMARY KEY (user_id, genre)
);

-- Friendship: symmetric relationship, but the REQUEST is directional.
-- Store direction + status, enforce one row per pair. Mishandling this is the
-- single most common bug in social-graph projects.
CREATE TABLE friendships (
    requester_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    addressee_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    status        TEXT NOT NULL CHECK (status IN ('pending','accepted','blocked')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (requester_id, addressee_id),
    CHECK (requester_id <> addressee_id)
);
-- Enforce one row per unordered pair (prevents A→B and B→A both existing):
CREATE UNIQUE INDEX friendship_pair_uniq
    ON friendships (LEAST(requester_id, addressee_id),
                    GREATEST(requester_id, addressee_id));

-- Events cached from the API, keyed by external id.
CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_event_id     TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    artist_id       UUID REFERENCES artists(id),
    venue_name      TEXT,
    metro_id        TEXT,
    starts_at       TIMESTAMPTZ,
    genre           TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User marks interest. Powers both matching and notifications.
CREATE TABLE event_interest (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    event_id   UUID REFERENCES events(id) ON DELETE CASCADE,
    level      TEXT NOT NULL CHECK (level IN ('going','maybe')),
    PRIMARY KEY (user_id, event_id)
);

-- Phase 4: expanded taste set (adjacent artists derived from Spotify related-artists).
CREATE TABLE user_taste_artists (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    artist_id  UUID REFERENCES artists(id) ON DELETE CASCADE,
    source     TEXT NOT NULL CHECK (source IN ('explicit','related')),
    score      REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (user_id, artist_id)
);

-- Phase 5: idempotency ledger so the job never double-notifies.
CREATE TABLE notifications_sent (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    event_id   UUID REFERENCES events(id) ON DELETE CASCADE,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);

-- Push tokens. Refresh on rotation or notifications silently die.
CREATE TABLE device_tokens (
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL,
    platform    TEXT NOT NULL CHECK (platform IN ('ios','android')),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (token)
);
```

---

## Ticketmaster Discovery API — endpoints you'll actually hit

Base: `https://app.ticketmaster.com/discovery/v2/`  (pass `apikey=` on every call)

- **Pull music events for a metro** (your scheduled cache job):
  `events.json?classificationName=music&dmaId={DMA}&apikey=...`
- **Resolve an artist name → attractionId** (Phase 1 artist entry):
  `attractions.json?keyword={name}&apikey=...`
- **Events for a specific artist:**
  `events.json?attractionId={id}&apikey=...`
- Watch the `Rate-Limit-Available` response header; back off at 429.

Spotify (Phase 4): use the artist search + **related artists** endpoints to build the
expanded taste set. Resolve names → Spotify IDs once and store them on the `artists` row.

---

## The two hard spots (brace for these)

**Artist similarity (Phase 4).** The clean approach: resolve each liked artist to a
Spotify ID, pull related artists + genres, store as an expanded taste set. Get this
version working before reaching for embeddings — it's 80% of the magic for 20% of the
effort, and it's the part interviewers find interesting.

**Notification fan-out (Phase 5).** Scheduled, not request-driven. The three traps *are*
the learning: idempotency (don't double-notify), deduplication (one digest, not five
pings), rate-sanity (per-metro pulls, cache hard). Use a real job queue.

---

## Mobile gotchas checklist

- [ ] **Request notification permission**, capture the device push token, store it, and
      **refresh it on rotation.** Stale tokens are the silent killer of push features —
      handle refresh from day one.
- [ ] **Never trust the client for matching.** All scoring + fan-out server-side.
- [ ] **Token-based auth** with secure on-device storage. No session cookies.
- [ ] **Build Phase 1 to be useful solo** so the app isn't empty before friends join.
- [ ] **Match on metro, never raw coordinates.** Decide location precision before the
      social graph exists, not after.

---

## Testing

- **Phase 1 test plan:** `docs/PHASE-1-TEST-PLAN.md` — full end-to-end checklist for the
  single-user feed (auth, taste entry, event sync, feed, mobile). Read it before testing
  Phase 1. Key gotcha documented there: with no Ticketmaster API key the app runs in
  **stub mode**, where genre matching is testable but artist matching is not (the stub
  resolver returns no `tm_attraction_id`).
- **Active virtualenv is `.venv/` at the repo root** (use `.venv/Scripts/python.exe`),
  not `backend/venv/`.

---

## What "done" looks like at each ambition level

- **Minimum demoable portfolio piece:** Phases 1–3. Solo feed → friend graph → "who'd go
  with you" matching. Legitimate and shows real full-stack + authz work.
- **Impressive version:** add Phase 4 (taste model) and Phase 5 (idempotent pipeline).
  These are the two time sinks, so treat them as upgrades after the core works end to end.

> A working simple version you can show beats an ambitious half-built one in every
> interview.
