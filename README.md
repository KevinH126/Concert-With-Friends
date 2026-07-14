# Concert With Friends

A mobile app that surfaces concerts coming to your area and which of your friends would want
to go with you. You enter your favorite artists and genres, connect with people you already
know, and get a ranked feed of upcoming shows — each one annotated with the friends who've
said they're going and the friends the app predicts would be into it.

It's built as a **closed friend graph** — your real friend group, not strangers. That avoids
the cold-start problem of open-graph social apps, keeps match predictions meaningful, and
bounds the event-sync workload.

> **Status:** the core loop is shipped and live — an async FastAPI backend on Render with a
> TDD-tested relevance scorer, ranked feed, social graph, full genre subsystem, and
> Ticketmaster integration, plus a React Native (Expo) client. The notification pipeline, push
> delivery, external taste-import, and in-app chat are designed but not yet built. See
> [Build status](#build-status).

---

## How it works

The system is organized around a few core constraints:

- **All matching and scoring is server-side.** The app is a thin, stateless view — taste
  models and friends' data never reach the client, which keeps authorization simple.
- **Ticketmaster is cached on a schedule, never per-user on page load.** Dual write-through
  caches (scheduled per-metro discovery + per-favorite-artist "anywhere") keyed on external
  IDs, under a 5,000-call/day ceiling. The one interactive call is a debounced artist
  typeahead.
- **Matching is on metro/city, never raw coordinates.** GPS is read once at onboarding to
  resolve a Ticketmaster metro (DMA), then discarded — never stored, never matched on.

Two pieces worth calling out:

- **Pure-function relevance scorer** (`backend/app/services/matching.py`, built test-first).
  `score(taste_set, event, ctx)` is a weighted blend of artist-tier affinity, hierarchical
  genre matching (your "Rock" matches rock sub-genres, with sub-genres scoring higher), a
  Ticketmaster popularity proxy, friend-shared interest, and your own marked interest.
- **Two taste-set variants for a privacy split.** Friend-visible predictions are built only
  from your explicit picks plus *shared* marks; your own feed ranking uses everything,
  including private marks. This prevents a private interest from leaking through a
  friend-visible prediction.

## Tech stack

| Layer | Choice |
|---|---|
| Client | React Native (Expo SDK 54), TypeScript, React Navigation |
| Backend | Python / FastAPI (async-first) |
| Database | PostgreSQL — SQLAlchemy 2.0 async + asyncpg, Alembic migrations |
| Auth | JWT (python-jose), bcrypt password hashing |
| Job queue | Celery + Redis (notification pipeline fan-out) |
| Real-time | WebSockets (in-app chat) |
| External data | Ticketmaster Discovery API; Spotify / Last.fm (later) |
| Deploy | Render — web API + managed Postgres |
| Dev infra | Docker Compose (local Postgres + Redis) |

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
`POST /admin/sync-genres` (once, to load the genre taxonomy) then `POST /admin/sync/{metro_id}`
per metro.

### Mobile

```bash
cd mobile
npm install
npm run tunnel     # tunnel mode — LAN mode is blocked on the dev network
```

Scan the QR code with Expo Go. Point the client at your local API or the live Render backend
via the API base URL in the app's config.

### Tests

```bash
cd backend
pytest              # needs a local Postgres 'concert_friends_test' database
```

Tests are written test-first where behavior is a spec: a full authorization matrix
(friends-only visibility, symmetric match disclosure, private-interest invisibility,
bidirectional blocking) and strict TDD on the scorer.

## Build status

```
P1    Solo feed                                       ✅ DONE
P1.5  Deploy the backend                              ✅ DONE (live on Render)
P2    Social graph + interest-marking                 ✅ DONE (verified on prod)
P3    Matching (ranked feed, search, compose-sheet)   ✅ DONE (verified on prod)
P3.5  UI pass                                         🔜 IN PROGRESS
P4    Notification pipeline                            ⬜ NOT BUILT (scaffolding only)
P5    Push delivery                                    ⬜ NOT BUILT
P6    Taste-set expansion (Spotify/Last.fm)            ⬜ NOT BUILT
P7    In-app chat                                      ⬜ NOT BUILT
```

## Further reading

- [`docs/PROJECT-REFERENCE.md`](docs/PROJECT-REFERENCE.md) — full technical reference:
  architectural decisions, database schema, and external-API notes
- [`docs/concert-buddy-build-plan.md`](docs/concert-buddy-build-plan.md) — the complete build
  plan
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — deployment and ops
```
