# Concert With Friends

A mobile app that tells you **which concerts are coming to your area and which of your
friends would actually want to go with you.** You enter your favorite artists and genres,
friend the people you already know, and get a ranked feed of upcoming shows — each one
annotated with the friends who've said they're going and the friends the app predicts
would be into it.

It's deliberately a **closed friend-graph** app (your real friend group, not strangers).
That design choice kills the cold-start problem that sank open-graph competitors, keeps
matching honest, and makes "favorites, anywhere" event sync cheap and bounded.

> **Status:** the core loop is **shipped and live** — async FastAPI backend on Render with
> a TDD-tested relevance scorer, ranked feed, social graph, full genre subsystem, and
> Ticketmaster integration, plus a React Native (Expo) client. The notification pipeline,
> push delivery, external taste-import, and in-app chat are designed but not yet built.
> See [Build status](#build-status) for the exact line.

---

## Why it's built this way

This is a portfolio piece built to be genuinely impressive for backend roles — and
"impressive" here means **fully deployed and live**, not a screenshot-only local demo. The
resume story is a deliberate, thorough backend organized around two centerpiece subsystems:

1. An **idempotent, deduplicated notification pipeline** — scheduled, not request-driven,
   with an at-least-once delivery guarantee (*a missed concert alert is worse than a rare
   duplicate*).
2. A **real-time WebSocket chat** for the people going to the same show.

The UX is "good enough not to embarrass the backend"; backend depth is the differentiator.
The core loop ships on its own first and the centerpieces layer on top, so a time crunch
leaves a working app plus one finished centerpiece rather than two stubs.

## Tech stack

| Layer | Choice |
|---|---|
| Client | React Native (Expo SDK 54), TypeScript, React Navigation |
| Backend | Python / FastAPI (async-first) |
| Database | PostgreSQL — SQLAlchemy 2.0 async + asyncpg, Alembic migrations |
| Auth | JWT (python-jose), bcrypt password hashing |
| Job queue | Celery + Redis (for the notification pipeline fan-out) |
| Real-time | WebSockets (in-app chat) |
| External data | Ticketmaster Discovery API; Spotify / Last.fm (later) |
| Deploy | **Render** — web API + managed Postgres |
| Dev infra | Docker Compose (local Postgres + Redis) |

## Architecture at a glance

A few non-negotiable constraints shape the whole system:

- **All matching and scoring is server-side.** The app is a thin, stateless view — taste
  models and friends' data never reach the client, and authorization stays clean.
- **Ticketmaster is cached on a schedule, never per-user on page load.** Dual write-through
  caches (scheduled per-metro discovery + per-favorite-artist "anywhere") keyed on external
  IDs, under a hard 5,000-call/day ceiling. The one allowed interactive call is a debounced
  artist typeahead.
- **Matching is on metro/city, never raw coordinates.** GPS touches the device once at
  onboarding to resolve a Ticketmaster metro (DMA), then is discarded — never stored,
  never matched on.

Two design decisions worth calling out:

- **Pure-function relevance scorer** (`backend/app/services/matching.py`, strict TDD).
  `score(taste_set, event, ctx)` is a weighted blend of artist-tier affinity, hierarchical
  genre matching (your "Rock" matches rock sub-genres, sub-genre scores higher), a
  Ticketmaster popularity proxy, friend-shared interest, and your own marked interest.
- **Two taste-set variants (a privacy split).** Friend-visible predictions are built only
  from your explicit picks plus *shared* marks; your own feed ranking uses everything
  including private marks. This provably keeps a private interest from leaking your taste
  through a friend-visible prediction.

## Repository layout

```
backend/          Async FastAPI service
  app/
    routers/      auth, users, friends, invites, artists, genres, events, feed, admin
    services/     matching (scorer), event_sync, ticketmaster, social
    models.py     SQLAlchemy 2.0 models
    worker.py     Celery app + beat schedule (pipeline scaffolding)
  alembic/        migrations
  tests/          pytest suite (100+ tests)
mobile/           React Native (Expo) client — 7 screens, theme tokens, shared components
docs/             Build plan, project reference, deploy guide, phase test plans
docker-compose.yml   Local Postgres + Redis
render.yaml          Render deploy config
```

## Running it locally

### Prerequisites

- Python 3.11+ and Node 18+
- Docker (for local Postgres + Redis)
- A Ticketmaster Discovery API key (optional — without one, genre matching still works but
  artist matching is stubbed)

### Backend

```bash
# 1. Start local Postgres + Redis
docker compose up -d

# 2. Create a virtualenv and install deps (use the repo-root .venv)
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 3. Configure env — create backend/.env
#    DATABASE_URL=postgresql://postgres:password@localhost:5432/concert_friends
#    SECRET_KEY=<any-random-string>
#    ADMIN_TOKEN=<any-random-string>
#    TICKETMASTER_API_KEY=<optional>

# 4. Run migrations and start the API
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

The API serves on `http://localhost:8000` (interactive docs at `/docs`).

**Seeding events:** event sync is currently manual via admin-token-protected endpoints —
`POST /admin/sync-genres` (once, to load the genre taxonomy) then
`POST /admin/sync/{metro_id}` per metro.

### Mobile

```bash
cd mobile
npm install
npm run tunnel     # tunnel mode — LAN mode is blocked on the dev network
```

Scan the QR code with Expo Go. Point the client at your local API or the live Render
backend via the API base URL in the app's config.

### Tests

```bash
cd backend
pytest              # needs a local Postgres 'concert_friends_test' database
```

The suite is test-first where behavior is a spec: a full authorization matrix
(friends-only visibility, symmetric match disclosure, private-interest invisibility,
bidirectional blocking) and strict TDD on the pure scorer.

## Build status

```
P1    Solo feed                                       ✅ DONE
P1.5  Deploy the backend                              ✅ DONE (live on Render)
P2    Social graph + interest-marking                 ✅ DONE (verified on prod)
P3    Matching (ranked feed, search, compose-sheet)   ✅ DONE (verified on prod)
P3.5  UI pass (lean-but-tasteful foundation)          🔜 IN PROGRESS
P4    Notification pipeline        ★ CENTERPIECE 1     ⬜ NOT BUILT (scaffolding only)
P5    Push delivery                                   ⬜ NOT BUILT
P6    Taste-set expansion (Spotify/Last.fm)           ⬜ NOT BUILT
P7    In-app chat                  ★ CENTERPIECE 2     ⬜ NOT BUILT
```

## Further reading

- [`docs/PROJECT-REFERENCE.md`](docs/PROJECT-REFERENCE.md) — full technical reference:
  every architectural decision, the database schema, external-API notes, and résumé bullets
- [`docs/concert-buddy-build-plan.md`](docs/concert-buddy-build-plan.md) — the complete
  build plan
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — deployment and ops
