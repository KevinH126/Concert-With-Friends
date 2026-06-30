# Phase 1 Test Plan — Single-User Feed

> **Purpose:** End-to-end verification that Phase 1 works before building the social graph (Phase 2).
> Phase 1 = **Auth + artist/genre entry + scheduled event cache pull + personal nearby-show feed.**
> It must be useful solo. This doc is written so any future session can execute it without re-deriving context.

**Status legend:** ⬜ not run · ✅ pass · ❌ fail (note the symptom + which test)

---

## 0. Scope

In scope for Phase 1 (test these):
- Signup / login / token auth (`/auth/*`)
- Profile + home-metro setting (`/users/me`)
- Favorite artists CRUD + name→canonical resolution (`/artists`)
- Favorite genres CRUD (`/genres`)
- Event cache sync for a metro (`/admin/sync/{metro_id}` + Celery beat)
- Personal feed: metro-scoped, matches artist **or** genre, upcoming-only (`/feed`)
- Event interest going/maybe (`/feed/events/{id}/interest`)
- Mobile app screens: Login, Taste, Profile, Feed

Out of scope (Phase 2+): friends, friend-aware matching, Spotify taste expansion, push notifications. Don't test those.

---

## 1. Prerequisites / environment

> **venv note:** the active virtualenv used in recent sessions is **`.venv/` at the repo root**, not `backend/venv/`. Use `.venv/Scripts/python.exe`. (`backend/venv` exists on disk but is untracked.) CLAUDE.md's `python -m venv venv` instructions describe a fresh setup; the working env here is `.venv`.

1. **Infra up:**
   ```bash
   docker-compose up -d            # Postgres on 5432, Redis on 6379
   docker ps                       # expect concert-with-friends-db-1 and -redis-1 "Up"
   ```
2. **Backend env:** `backend/.env` exists with a real `SECRET_KEY`. As of 2026-06-30 `TICKETMASTER_API_KEY` is **populated with a real key** → live mode by default; blank it to force stub mode for the deterministic checks (see §2).
3. **DB schema at head:**
   ```bash
   cd backend && ../.venv/Scripts/python.exe -m alembic current   # -> 6a15c3d72c6e (head)
   ```
   If a fresh DB: `alembic upgrade head`. If tables already exist unstamped: `alembic stamp head`.
4. **Run API:**
   ```bash
   cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --reload   # http://localhost:8000
   ```
   Swagger UI at `http://localhost:8000/docs` is the easiest way to drive these tests.
5. **Mobile (for §9 only):** set `BASE_URL` in `mobile/src/api/client.ts:5` to your machine's LAN IP (currently `http://192.168.1.85:8000`), then `cd mobile && npm install && npx expo start`.

Helper for curl tests (bash):
```bash
BASE=http://localhost:8000
TOKEN=""            # filled in after login; use:  -H "Authorization: Bearer $TOKEN"
```

---

## 2. CRITICAL testing consideration — stub mode vs. real API key

> **⚠️ Status update (2026-06-30):** `backend/.env` now contains a **real Ticketmaster
> API key**, so the app is **NOT in stub mode by default anymore.** A live sync hits the
> real API, and the stub assertions below (the fixed 3 events, `STUB_*` ids, the exact
> names/dates) will **not** appear — those tests "fail" only because the data source
> changed, not because anything is broken. To run the deterministic stub-mode checks in
> this section, **temporarily blank `TICKETMASTER_API_KEY=` and restart uvicorn**; restore
> the key afterward. With the key present you can instead run **Path B** directly to verify
> real artist matching (Test 8.3 / 9.3, exit criterion #4) — the one thing stub mode cannot do.

With `TICKETMASTER_API_KEY` empty, the app runs in **stub mode**:
- `resolve_artist()` returns `(None, <name>)` — user-added artists get **`tm_attraction_id = NULL`**.
- `fetch_events_for_metro()` returns 3 fixed stub events regardless of metro id:
  | tm_event_id | name | attraction id | genre | starts_at |
  |---|---|---|---|---|
  | STUB_EVT_001 | Radiohead Live | STUB_ATT_RADIOHEAD | Rock | 2026-08-15 |
  | STUB_EVT_002 | Thom Yorke Solo | STUB_ATT_THOM | Alternative | 2026-09-01 |
  | STUB_EVT_003 | Jazz Night | (none) | Jazz | 2026-07-20 |

**Consequence:** In stub mode, **genre-based feed matching is fully testable**, but **artist-based matching effectively is NOT.** A user who adds "Radiohead" gets an artist row with `tm_attraction_id=NULL`; the synced Radiohead event creates a *separate* artist row keyed by `STUB_ATT_RADIOHEAD`. The feed matches on `Event.artist_id`, so the two never line up.

**To fully verify artist matching (Test 8.3) you need a real (free) Ticketmaster API key** so `resolve_artist` returns the same `tm_attraction_id` the events carry. Two paths:
- **Path A (no key):** run everything except 8.3; mark 8.3 as "blocked — needs API key."
- **Path B (real key):** put a key in `backend/.env`, restart, use a real metro DMA (e.g. `345` = NYC, `324` = LA-ish — confirm via `attractions`/`dmas`), and a real artist with upcoming shows.
- **Path C (manual, no key):** verify the JOIN logic directly — after syncing, read the event's `artist_id` from the DB and insert a `user_artists` row pointing the test user at that exact id, then confirm the event appears. Documents that the query works even if the stub resolver doesn't link.

Note today's date in CLAUDE.md context is **2026-06-27**; stub events are all in the future relative to that, so "upcoming-only" filters keep them. If the real date has moved past 2026-09-01, the stub events will be filtered out of the feed — bump the stub dates in `backend/app/services/ticketmaster.py` `_stub_events()` if needed.

---

## 3. Health & infra ✅
- **3.1** `GET /health` → `200 {"status":"ok"}`.
- **3.2** Swagger `/docs` loads and lists auth/users/artists/genres/feed/admin routes.

---

## 4. Auth ✅
- **4.1 Signup happy path:** `POST /auth/signup` `{email, display_name, password}` → `201` + `access_token`. Save token.
- **4.2 Duplicate email:** repeat 4.1 same email → `409 "Email already registered"`.
- **4.3 Invalid email format:** `email:"notanemail"` → `422` (EmailStr validation; confirms `email-validator` is installed — regression for that bug).
- **4.4 Login happy path:** `POST /auth/login` correct creds → `200` + token.
- **4.5 Login wrong password:** → `401 "Invalid credentials"`.
- **4.6 Login unknown email:** → `401` (same message; no user enumeration).
- **4.7 `GET /auth/me` with token:** → `200` user object (id, email, display_name, home_metro_id, location_precision).
- **4.8 `GET /auth/me` no token:** → `401/403`.
- **4.9 `GET /auth/me` garbage token:** `Authorization: Bearer xxx` → `401`.
- **4.10 Password hashing sanity:** signup two users with the **same** password; confirm in DB their `hashed_password` differ (bcrypt salt). Optional.

---

## 5. Profile / metro ✅
- **5.1** `PATCH /users/me` `{home_metro_id:"345"}` → `200`, field updated; re-`GET /auth/me` confirms.
- **5.2** `PATCH /users/me` `{display_name:"New Name"}` → updates.
- **5.3** `PATCH /users/me` `{location_precision:"city"}` → accepted; `{"bogus"}` → silently ignored (stays previous value — current behavior, not an error).

---

## 6. Artists ✅
- **6.1 Add artist:** `POST /artists` `{name:"Radiohead"}` → `201`, returns `{id,name,tm_attraction_id,weight}`. In stub mode `tm_attraction_id=null`.
- **6.2 List:** `GET /artists` → contains Radiohead with weight 1.
- **6.3 Update weight (upsert):** `POST /artists` `{name:"Radiohead", weight:3}` → same artist, weight now 3, **no duplicate** in list.
- **6.4 Case-insensitive dedup (regression):** `POST /artists` `{name:"radiohead"}` → must **not** create a second artist row (matches `func.lower`). List still has one Radiohead.
- **6.5 Remove:** `DELETE /artists/{artist_id}` → `204`; gone from list.
- **6.6 Remove not-in-list:** `DELETE /artists/{random-uuid}` → `404`.
- **6.7 (Path B only) Real resolution:** with API key, add a real artist → `tm_attraction_id` populated and `name` canonicalized.

---

## 7. Genres ✅
- **7.1 Add:** `POST /genres` `{genre:"Rock"}` → `201`, returns list incl "Rock".
- **7.2 Dedup:** add "Rock" again → no duplicate; list unchanged.
- **7.3 List:** `GET /genres` → `["Rock", ...]`.
- **7.4 Remove:** `DELETE /genres/Rock` → `204`; gone.
- **7.5 Remove missing:** `DELETE /genres/Nope` → `404`.

---

## 8. Event sync ✅
- **8.1 Trigger sync (stub):** `POST /admin/sync/345` header `X-Admin-Token: <SECRET_KEY value from backend/.env>` → `200 {"events_upserted":3}`.
- **8.2 Admin auth:** same call with wrong/no token → `403`.
- **8.3 Data landed:** query DB `SELECT name, genre, starts_at, artist_id FROM events;` → 3 rows; `starts_at` is a real **timestamptz** not a string (regression for the datetime bug), Radiohead/Thom rows have non-null `artist_id`, Jazz row null.
- **8.4 Artist rows created (regression):** `SELECT name, tm_attraction_id FROM artists WHERE tm_attraction_id LIKE 'STUB_ATT%';` → Radiohead + Thom Yorke rows exist (sync now creates/links artists).
- **8.5 Idempotent upsert:** run 8.1 again → still 3 events total (upsert on `tm_event_id`, no duplicates).
- **8.6 (Optional) Celery path:** start worker + beat (`celery -A app.worker worker` / `beat`), or call the task directly, and confirm `sync_metro_task` runs twice in a row without "event loop" errors (regression for the per-task engine fix). Note beat is hardcoded to metro `DMA_123` in `app/worker.py`.

---

## 9. Feed ✅
Set up: one test user with `home_metro_id=345`, genre "Rock" added, and a completed sync (§8).
- **9.1 Metro gate:** new user with **no** `home_metro_id` → `GET /feed` → `400` mentioning `home_metro_id`.
- **9.2 Genre match:** user with genre "Rock", metro 345 → feed includes **Radiohead Live** (Rock). (Stub events have no metro filter applied at fetch, but they're stored with `metro_id=345` from the sync call, so the feed's `metro_id` filter matches only if you synced metro `345`. Sync the **same** metro id the user has.)
- **9.3 Artist match:** see §2 — Path B or C. Add the artist that owns a synced event; confirm that event appears even if the user has no matching genre.
- **9.4 No matches:** user with metro set but **no** artists and **no** genres → `GET /feed` → `[]` (empty, not error).
- **9.5 Upcoming-only:** confirm only future events show. To test the filter, temporarily set a stub event's date in the past (or DB-update `starts_at`) → it disappears from feed.
- **9.6 Ordering:** with multiple matching events, results sorted by `starts_at` ascending.
- **9.7 Set interest:** `PUT /feed/events/{event_id}/interest` `{level:"going"}` → `200`; `GET /feed` shows `my_interest:"going"`.
- **9.8 Update interest:** same endpoint `{level:"maybe"}` → now `"maybe"` (no duplicate row).
- **9.9 Invalid level:** `{level:"banana"}` → `422`.
- **9.10 Interest on missing event:** `PUT .../{random-uuid}/interest` → `404`.
- **9.11 Remove interest:** `DELETE /feed/events/{event_id}/interest` → `204`; feed shows `my_interest:null`.

---

## 10. Mobile end-to-end ✅
Run against the live backend (BASE_URL = LAN IP). Use Expo Go or a simulator.
- **10.1 Signup** from Login screen → lands in tabbed app (Feed/Taste/Profile).
- **10.2 Persisted session:** kill & reopen app → still logged in (token in AsyncStorage).
- **10.3 Taste tab:** add an artist and a genre → chips appear; remove each → chips disappear.
- **10.4 Profile tab:** set Home Metro → "Saved"; field stays populated after reload (regression for the stale-field fix). Metro id should be the one you synced.
- **10.5 Feed tab — empty/needs-metro states:** before metro set, Feed shows the "Set your home metro" message; before matches, shows "No upcoming shows match your taste."
- **10.6 Feed tab — populated:** after metro + genre + sync, events list renders (name, venue, date, genre chip).
- **10.7 Interest buttons:** tap Going/Maybe → highlights; tap again → clears. Pull-to-refresh reloads.
- **10.8 401 handling (regression):** invalidate the token (e.g. change SECRET_KEY server-side and restart, or wait out expiry) → next request bounces the app back to the Login screen instead of erroring silently.
- **10.9 Logout:** Profile → Sign out → returns to Login; reopening app stays logged out.

---

## 11. Regression checklist (bugs fixed in the error-review pass)
These map to specific earlier fixes — quick confirmations:
- [ ] App imports/boots at all → `email-validator` present (Test 4.3 covers it).
- [ ] Event sync stores real datetimes, not strings (Test 8.3).
- [ ] Sync creates + links artist rows (Test 8.4).
- [ ] Case-insensitive artist dedup (Test 6.4).
- [ ] Celery task runs repeatedly w/o cross-loop errors (Test 8.6).
- [ ] Alembic migration is real and DB at head (Prereq §1.3).
- [ ] Mobile 401 → logout (Test 10.8); Profile metro field not stale (Test 10.4).

---

## 12. Exit criteria for Phase 1
Phase 1 is "done enough to move to Phase 2" when:
1. A brand-new user can sign up, set a metro, add a genre, and **see a relevant cached event in the feed** — entirely solo, on the mobile app.
2. Marking interest (going/maybe) persists and reflects on reload.
3. Event sync is idempotent and schedulable (manual admin trigger verified; Celery path at least smoke-tested).
4. Artist-based matching verified via Path B **or** Path C (don't ship Phase 1 claiming artist match works if only stub mode was tested).
5. All §11 regressions confirmed.

Record results inline (flip ⬜→✅/❌). File issues for any ❌ before starting Phase 2.

---

## 13. Run log

### Pass 1 — stub mode, API only (2026-06-30)
Ran with `TICKETMASTER_API_KEY` temporarily blanked; key restored afterward. Driven via curl + psql.

- **§3 Health/infra ✅**, **§4 Auth ✅**, **§5 Profile ✅**, **§6 Artists ✅**, **§7 Genres ✅**,
  **§8 Event sync ✅** (sync=3, idempotent re-run still 3, real `timestamptz`, artists linked,
  stub artist rows present), **§9 Feed ✅** (metro gate, genre match, no-match `[]`, ascending
  order, upcoming-only filter, interest going→maybe single-row, invalid level 422, missing event
  404, remove interest). **§8.6 Celery ✅** — `sync_metro_task('345')` run twice back-to-back, no
  cross-loop error, returned 3 each time.
- **Deviations (minor, not bugs):**
  - §8.2: admin sync with **no** `X-Admin-Token` header returns **422** (FastAPI missing-required-header
    validation), not 403. The wrong-token case correctly returns 403.
  - §6.4: case-insensitive dedup correctly keeps one row, but re-adding `radiohead` with no `weight`
    **resets weight to the default 1** (had been 3 from §6.3). Harmless; test only asserts no duplicate.
  - §9.1: the 400 detail text says "PATCH **/auth/me** with home_metro_id" but the working endpoint
    is **/users/me**. Cosmetic message inaccuracy.
- **Not run in Pass 1:** §8.3 real resolution / §9.3 artist match (Path B — needs the real key + a
  real DMA/artist), §10 mobile (needs device/Expo), §4.10 & §5.3 bogus-value DB spot-checks (optional).

### Pass 2 — real mode (2026-06-30)
Real `TICKETMASTER_API_KEY` in `backend/.env`; uvicorn restarted in live mode.

- **Key valid ✅** — direct TM calls succeed; `dmaId=345` (NYC) reports 1,955 music events.
- **🐞 BUG FOUND → ✅ FIXED — large-metro sync 500s (deep-paging cap).** `POST /admin/sync/345`
  originally → **500**. `fetch_events_for_metro` paged with `size=200` until `totalPages`, but
  Ticketmaster rejects any request past **offset 1000** (`size × page > 1000`) with **400**, and
  `_get_with_backoff` re-raised non-429 errors, so the whole sync aborted and upserted **nothing**
  (verified: 0 real events landed). Stub mode (3 events) never paged, so this was invisible until
  now. Impacted NYC — the primary demo metro — and any market with >1000 events (`345`=1955,
  `382`=1323, `273`=1004; `247`=371, `287`=328, `218`=437 were already safe).
  **Fix applied** in `app/services/ticketmaster.py`: page only up to the `_MAX_RESULTS=1000`
  cap (events are date-asc, so we keep the soonest ~1000), and the per-page fetch now catches
  `httpx.HTTPError` so a stray HTTP error / **timeout** keeps what was already fetched instead of
  crashing the run. **Re-verified:** `POST /admin/sync/345` → `200 {"events_upserted":1000}`,
  idempotent across repeated runs, NYC feed returns real events (404 Rock matches for a test user),
  small metro `287` still `328`. A transient `httpx.ReadTimeout` once surfaced on a re-run (real
  API slowness, not a logic bug); the new `httpx.HTTPError` catch now absorbs that once any page
  has landed.
  **Follow-up (P4, not P1):** the 1000-cap silently drops events beyond the soonest 1000, which is
  fine for the feed but **wrong for the nightly pipeline diff** — full coverage needs date-windowed
  queries. File before P4:
  ```
  gh issue create \
    --title "Sync: date-window large-metro pulls to beat the TM 1000-item deep-paging cap" \
    --body "fetch_events_for_metro caps at 1000 events (TM rejects deeper paging). Fine for the P1 feed (soonest-1000), but the P4 nightly diff needs every event or it will miss alerts. Split the per-metro query into date windows (each <1000 items) and merge. Affected metros today: 345 (1955), 382 (1323), 273 (1004)."
  ```
  **Filed:** [#1 — Sync: date-window large-metro pulls to beat the TM 1000-item deep-paging cap](https://github.com/KevinH126/Concert-With-Friends/issues/1) (label: `enhancement`).
- **Artist matching ✅ (Path B, exit criterion #4)** — synced the smaller `dmaId=287` (328 events,
  upserted cleanly). Created a fresh user with metro `287` and **no genres**, added artist
  `Josh Groban`; `resolve_artist` populated `tm_attraction_id=K8vZ9175jS0` — the **same** id the
  synced event carries (canonical artist row deduped/reused) — and `/feed` returned exactly that
  one event. With no genres, the only possible match path is the artist, so artist matching is
  proven against real data.
- **Real-world wrinkle noted:** `resolve_artist` takes `attractions[0]` with `size=1`; searching a
  non-touring band ("Radiohead") returns a **tribute act** ("Just Radiohead") as the top hit.
  Acceptable for now, but typeahead/disambiguation (P-later) should revisit.
- **§10 mobile:** see Pass 3 below.

### Pass 3 — mobile end-to-end (2026-06-30)
Real iOS device (Expo Go, `192.168.1.62`) against the backend bound to `0.0.0.0:8000`
(reachable at `192.168.1.85:8000`; firewall was *not* a problem). Every step confirmed
server-side from the uvicorn access log as the tester tapped.

- **All §10 steps pass:** 10.1 signup (201 + auto `auth/me`), 10.2 persisted session
  (reopen → `auth/me` 200, no re-login), 10.3 taste CRUD (POST/DELETE artists+genres),
  10.4 metro persists (PATCH 200; `home_metro_id=345` survives reload — stale-field fix holds),
  10.5 **both** empty states (the `GET /feed` 400 metro-gate → "Set your home metro", then 200
  empty → "No upcoming shows match your taste"), 10.6 populated feed (real NYC events render),
  10.7 interest going/clear/maybe + pull-to-refresh, 10.8 401→logout (rotated `SECRET_KEY`,
  restarted, restored), 10.9 explicit sign-out stays signed out on reopen.
- **🐞 BUG FOUND → ✅ FIXED — Feed didn't refresh on tab focus.** Changing taste on the Taste
  tab and returning to Feed showed stale results; only a full app restart updated it. Cause:
  `FeedScreen` loaded in a mount-only `useEffect`, but the tab navigator keeps the screen
  mounted, so it never refetched. **Fix:** `mobile/src/screens/FeedScreen.tsx` now reloads via
  `useFocusEffect` (existing list stays visible during refetch — no spinner flicker). Verified
  live on device: removing/adding a genre updates the feed immediately, no restart.
- **⚠️ Known gap (not a bug) — free-text genres exact-match against TM strings.** Typing
  `Hip Hop` returns nothing because Ticketmaster stores the genre as **`Hip-Hop/Rap`**; `Rock`,
  `Jazz`, `Pop` etc. work because they match exactly. This is the free-text genre box vs. the
  build plan's locked **"genre picker from TM taxonomy"** decision. Tracked in
  [#2](https://github.com/KevinH126/Concert-With-Friends/issues/2) (label: `enhancement`).
