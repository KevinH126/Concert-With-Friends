# Concert-With-Friends — Build Plan

A mobile app where you enter your favorite artists/genres, friend people you already
know, and get told **which concerts are coming and which of your friends would actually
want to go with you.**

## Thesis (read this first)

This is a **portfolio piece built to be genuinely impressive for backend roles** — and
"impressive" explicitly includes being **fully deployed and live**, not a local,
screenshot-only demo. The resume story is a *deliberate, thorough backend* with two
real, finished centerpiece subsystems:

1. **An idempotent, deduplicated notification pipeline** (scheduled, not request-driven).
2. **A real-time in-app chat system** for people going to the same show.

UX should be good enough not to embarrass the backend, but the backend depth is the
differentiator. A working app + one finished centerpiece beats two half-built ones — so
the **core loop is shippable on its own first**, and the centerpieces come after it.

### Scoping decision

Build the **closed friend-graph** version, for a real friend group (yours), not strangers.
This is deliberate:

- It kills the cold-start problem that sank every competitor (Radiate, Beatmatch, etc.).
  A friends-only app is useful the moment your ten friends join, because the trust already
  exists.
- It is a cleaner system to design and gives a working demo with **real data**.
- The closed graph also makes the "favorites, anywhere" event sync *cheap and bounded*
  (see the two-cache decision below) — a strangers app could never afford it.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Client | React Native (Expo) — `mobile/` | Expo wraps APNs + FCM behind one push API |
| Backend | Python/FastAPI — `backend/` | Async-first; fast to build |
| Database | **PostgreSQL** (SQLAlchemy async + asyncpg) | Domain is all relationships → join tables + FKs |
| Job queue | Celery + Redis | Notification pipeline fan-out (centerpiece 1) |
| Real-time | WebSockets (chat) | In-app chat (centerpiece 2) |
| External data | Ticketmaster Discovery API (events + artist/genre taxonomy), Spotify API (taste expansion, later) | Free tiers cover a personal project |

**Non-negotiables (architectural constraints):**
- All matching/scoring happens **server-side**. The app is a thin view. Keeps taste
  models and friends' data off the device and keeps the authz story clean.
- Token-based auth (JWT) with secure on-device token storage. No session cookies for a
  mobile client.
- **Cache Ticketmaster on a schedule, never per-user on page load.** Watch the
  `Rate-Limit-Available` response header; back off at 429. (The *one* allowed per-user,
  interactive TM call is artist typeahead search — debounced, min-length, write-through
  cached. See the artist-search decision.)
- Match on **metro/city, never raw coordinates.** Coordinates may touch the device once
  at onboarding to resolve a metro, then are discarded — never stored, never matched on.

**API limits to design around:**
- Ticketmaster free tier: **5,000 calls/day, 5 req/sec.** Cache aggressively; pull
  per-metro and per-favorite-artist on a schedule.

---

## Dev commands

**Active virtualenv is `.venv/` at the repo root** (`.venv/Scripts/python.exe`), **not**
`backend/venv/`.

**Start infrastructure (Postgres + Redis):**
```
docker-compose up -d
```

**Backend:**
```bash
cd backend
# Use the repo-root .venv (already created):
source ../.venv/Scripts/activate                       # Windows (Git Bash)
pip install -r requirements.txt
cp .env.example .env   # then fill in SECRET_KEY (and TICKETMASTER_API_KEY for real data)
uvicorn app.main:app --reload                          # API at http://localhost:8000
```

> **Stub mode:** with no `TICKETMASTER_API_KEY`, the app runs in stub mode — genre
> matching is testable but artist matching is not (the stub resolver returns no
> `tm_attraction_id`). Real artist search/matching needs a key.

**Run backend tests** (local Docker Postgres must be up; creates `concert_friends_test`):
```bash
cd backend
../.venv/Scripts/python.exe -m pytest -q
```

**Run DB migrations:**
```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

**Celery worker + beat (event sync + notification pipeline — arrives in P4):**
```bash
cd backend
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info
```

**Manually trigger an event sync** (no Celery needed — this is the P1 sync mechanism):
```
POST /admin/sync/{metro_id}   Header: X-Admin-Token: <SECRET_KEY>
```

**Mobile:**
```bash
cd mobile
npm install
npx expo start
```
Change `BASE_URL` in `mobile/src/api/client.ts` to your machine's LAN IP when testing on a
physical device. **Mobile is not continuously deployed** — it stays in Expo dev. A
store-installable build (EAS/TestFlight) is a later nicety, not part of the thesis.

---

## Phase roadmap

Build order is deliberate and differs from a naive 1→5: **deploy early**, reach the
headline pipeline **before** the open-ended Spotify work, and keep the core loop shippable
on its own.

```
P1    Solo feed                              ✅ done (sync is MANUAL, not scheduled yet)
P1.5  Deploy the backend                     ✅ done (live on Render)
P2    Social graph + interest-marking        ✅ done (verified on prod)
P3    Matching  (+ ranked feed, event search, compose-sheet hand-off)   ← next
P3.5  UI pass                                (after P3 reshapes the feed card; before P4)
P4    Notification pipeline                   ★ CENTERPIECE 1
P5    Push delivery  (+ onboard the real friend group)
P6    Taste-set expansion (Spotify)
P7    In-app chat                             ★ CENTERPIECE 2
P8+   Backlog
```

### P1 — Solo feed *(done)*
Sign up → enter artists/genres → see nearby concerts. Forces auth, DB, the third-party
API, and caching into place.
- [x] Auth (email signup/login, JWT issuance, secure storage on device)
- [x] Enter favorite artists → resolve to a canonical artist row
- [x] Enter favorite genres
- [x] Pull events per metro from Ticketmaster into the `events` cache
- [x] Feed: upcoming nearby events matching the user's artists/genres
- **Honest status:** the event sync is **manual** (`POST /admin/sync/{metro_id}`).
  *Scheduled* sync (Celery beat) arrives with the pipeline in **P4**. P1's checklist line
  about a "scheduled job" was aspirational — it's manual today.

### P1.5 — Deploy the backend *(immediate next)*
Deploy now, while the surface is small (web API + Postgres), then ship every later phase
to prod. Don't stack deployment (hard) on top of the pipeline (hardest) at the end.
- [ ] **Pick a deployment target** *(open decision — next thing to grill)*: managed
      Postgres, where the worker + beat processes run, secrets, migrations on a real DB.
- [ ] Web API + Postgres live first.
- [ ] Redis + worker + beat added to prod when **P4** needs them, on infra you already
      understand.
- [ ] Each later phase = merge → migrate → deploy. Production is never a cliff.

### P2 — Social graph + interest-marking *(grilled + locked 2026-07-01)*
- [ ] **Discovery — invites:** multi-use token (cap ~25 redemptions, ~7-day expiry,
      revocable). Share artifact = `GET /invites/{token}` **HTML landing page** on the API
      ("Kevin invited you — open the app and enter this code"); the in-app "enter invite
      code" screen accepts the raw code **or** the pasted URL; QR = that URL rendered.
      No deep links until a store build exists. Redemption happens **post-signup**
      (optional invite-code field on the signup screen).
- [ ] **Redeeming = instant `accepted` friendship** (requester = inviter). Generating the
      link *is* consent — no approval step for people you invited. Schema change:
      `invites.accepted_by` → an `invite_redemptions` audit table.
- [ ] **Discovery — username search:** username **required at signup** (nullable in DB for
      legacy accounts, who set it via profile); lowercase, 3–20 chars, `[a-z0-9_]`,
      unique, stored normalized. Search = **prefix match, min 3 chars**, ~10 results,
      excludes self + blocked pairs; each result carries friendship status so the UI
      draws the right button.
- [ ] **Friend requests with mutual consent** (request → accept/decline) for the
      search path. **Decline, cancel-request, and unfriend all DELETE the row** — clean
      slate, either side may re-request; no `declined` tombstone.
- [ ] **Block = full mutual severance, silent.** Deletes any pair row, writes
      `status='blocked'` with requester = blocker. Both directions: hidden from search,
      requests fail generically, taste/interest invisible. Blocked user is never told;
      only the blocker can unblock (delete → clean slate). Accepted edge: one row per
      pair means the blockee can't also record a block.
- [ ] **Interest-marking** (`going`/`maybe`) — pulled forward into P2 because it's the
      highest-signal input to *both* matching and notifications. Upsert + delete-to-clear;
      markable on any event by id, not just feed-matched ones.
- [ ] **Private-interest flag from day one:** marking interest privately still feeds *your
      own* notifications and feed, but is hidden from friends and excluded from the match
      results friends see about you.
- [ ] **Authz, decided explicitly:** taste + interest are **friends-only by default**;
      match disclosure is **symmetric** (mutual friends see each other's likely-match);
      location exposure is metro-grained. (Per-artist taste hiding → backlog.)
- [ ] **Where it surfaces (two screens):** (1) **friend profile** — display name,
      username, metro, artists w/ favorite–liked tier, genres, upcoming shared-visibility
      interests; (2) **friends-on-feed strip** — event cards show which friends marked
      shared interest ("Sam and Alex are going"). The strip is the seam P3's match scores
      slot into. (No push until P5 — pending requests surface via the Friends tab on app
      open.)
- [ ] **Testing:** first automated pytest suite. **Authz matrix written test-first**
      (non-friend sees nothing / friend sees shared-only / private invisible / block
      hides both directions / double-request rejected); CRUD tests-after; plus
      `docs/PHASE-2-TEST-PLAN.md` manual mobile checklist.
- **Done when:** two real accounts become friends and see each other's permitted taste +
  interest — and the authz suite is green.
- **Honest status: ✅ DONE (2026-07-01).** Deployed to prod (migration + auto-deploy);
  52-test suite green; full `PHASE-2-TEST-PLAN.md` walked on prod with live accounts —
  invite landing/instant-accept/idempotent re-redeem, request→accept via search,
  friend profile authz, shared-vs-private interest in both directions, block (incl.
  block-beats-invite, scoped to the pair). Known gaps (small, non-blocking): unblock
  and invite-revoke have no mobile UI (API only). Test accounts left on prod:
  test_buddy / invite_pal (@example.com emails).

### P3 — Matching *(grilled + locked 2026-07-01)*
Matching **plus the feed's ranking brain** — one pure scorer used everywhere.
- [ ] **Scorer (strict TDD, pure function):** `score(taste_set, event, ctx)` = weighted
      sum of direct artist match (favorite > liked tier) + **hierarchical** genre match
      (sub-genre > broad; a user's "Rock" matches rock sub-genres) + artist popularity +
      friend-shared-interest (own-feed ranking) + own-marked-interest. The signature
      **reserves an in-range/travel input** (constant in P3 — infra deferred, below).
      Weights/thresholds/buckets are named tunable constants in
      `backend/app/services/matching.py`.
- [ ] **The scorer takes a *taste-set* as input from day one** — assembled **in-memory**
      from `user_artists` + `user_genres` at request time. **No `user_taste_artists`
      table in P3** (mirroring explicit picks = dual-write drift risk). P6 creates a
      table for Spotify `related` rows *only*; the assembler unions it in; the scorer
      never notices. "Taste-set from day one" is a *signature* promise, not storage.
- [ ] **Feed is re-ranked** (chronological is dead): one list ordered by relevance score
      with a **time-proximity boost** (nearer shows get a modest multiplier decaying over
      ~90 days). A favorite artist months out still tops the list; among comparable
      matches, sooner wins.
- [ ] **Popularity term — TM proxy now, Spotify at P6:** store the attraction's
      `upcomingEvents` count on `artists` during event sync (already in the response,
      zero extra calls). Sinks random cafe-band genre matches below touring acts. P6
      swaps in Spotify popularity; scorer shape unchanged.
- [ ] **Full genre subsystem** (the P1 free-text box dies): fetch `classifications.json`
      into a `tm_genres` reference table (name + parent), genre **picker** UI, parse +
      store `subGenre` on events during sync, `is_subgenre` flag on `user_genres`. Also
      fixes the silent case-mismatch bug free-text matching has today.
- [ ] **Friend matching:** rank friends per event; **symmetric** disclosure; private
      interest never feeds friend-visible results (not even as a scorer input). **One
      strip** per card, ordered marked-going > marked-maybe > predicted. Prediction =
      **two wording buckets** ("would probably go" / "might be into this"), weak hidden;
      **no numbers or meters** (false precision from hand-tuned v1 weights — the bucket
      rides in the API so P3.5 can re-skin it as stars later if the scorer earns it).
- [ ] **Social pull-in:** feed inclusion = taste match **OR ≥1 friend with shared
      going/maybe** — a friend's real interest beats a genre match as a signal; the
      strip explains why the card is there ("Sam is going").
- [ ] **Event search:** `GET /events/search?q=` over the **cached metro events**
      (name/artist/venue) + a search bar on the feed screen. Closes the "mark interest
      on any show" gap (the API has allowed it since P2; the UI had no path to find
      non-matching events). Never a live TM call.
- [ ] **Compose-sheet chat hand-off:** button appears at **≥1 friend with shared marked
      interest** (you + one friend *is* a plan; the plan's old "≥2" would ~never fire in
      a small graph). Predicted friends are listed as suggested invitees but never
      trigger it. Share text = event name/venue/date + TM link (store `events.url` at
      sync). In **P7** the button points *inward* to in-app chat instead.
- [ ] **Travel-willingness infra DEFERRED** (metros table, centroids, travel-tier
      columns, per-favorite-artist anywhere-sync): with no anywhere-sync there are zero
      cross-metro events for an in-range term to distinguish — it would be dead code. It
      lands with P4's scheduled jobs; the scorer's reserved input means nothing rewrites.
- [ ] Scoring computes **inline at `GET /feed`** — closed graph (~10 friends × a few
      hundred events) is trivial; no precompute before P4's job infra exists.
- **Done when:** the feed is ranked and searchable, and event cards tell you *who* to go
  with — marked friends first, predicted friends labeled by confidence.

### P3.5 — UI pass *(added 2026-07-01)*
Deliberately scheduled **after P3** (matching reshapes the feed card — the app's
centerpiece screen — so polishing it earlier is rework) and **before P4** (the pipeline
is ~pure backend, so this delays nothing, and demos look good during the P4 grind).
Must land before real friends onboard at P5 — first impressions happen then.
- [ ] Extract `theme.ts` (colors/spacing/radii) + shared components (`Button`, `Card`,
      `Chip`) — **start using these from the first P3 screen onward**; the pass then
      becomes a re-skin, not a rewrite.
- [ ] Visual identity: pick the look from a reference folder (collect screenshots
      during P3 — Songkick / Bandsintown / Dice event cards are the comps).
- [ ] Feed card redesign around the P3 headline ("Sam and Alex would probably go").
- [ ] Navigation polish, empty states, loading states (skeletons over spinners).
- [ ] Sweep the hardcoded `#6200EE`s (~8 files) into the theme.
- **Scope guard:** this is a re-skin + consistency pass, not a redesign of flows. UX
  good enough not to embarrass the backend — the backend stays the differentiator.

### P4 — Notification pipeline ★ CENTERPIECE 1
Scheduled background job (Celery beat), not request-driven. This is the resume sentence.
- [ ] Nightly per-metro: pull → **diff** new events against the `events` cache (clean
      diff, keyed on `tm_event_id`).
- [ ] For each genuinely-new relevant event, **compute matched users** and enqueue.
- [ ] **Digest, don't spray:** collect *all* of a user's new relevant events for the run
      into **one** notification, never one ping per band. (Deduplication.)
- [ ] **Idempotency via the `notifications_sent` ledger** (`PK(user_id, event_id)`): run
      the job twice → second run sends nothing.
- [ ] **Failure dial = at-least-once with compensating claims.** Claim events with
      `INSERT ... ON CONFLICT DO NOTHING`, **commit the claim only after the push
      succeeds**, roll back the claim on send failure. Rationale: for concert alerts a
      *missed* notification is strictly worse than a rare *duplicate* — bias toward
      delivery, lean on the ledger + digest to keep dups rare.
- [ ] **Scope = new events only** for the nightly job. *New relevance* (a user adds an
      artist whose show was already cached) is handled separately by an **immediate
      check at add-time**, not the nightly diff.
- [ ] **Rate-sanity:** per-metro pulls, aggressive caching, stay under 5k/day.
- **"I built an idempotent, deduplicated notification pipeline and chose at-least-once
  delivery because a missed concert alert is worse than a duplicate" is the sentence that
  lands.**

### P5 — Push delivery
The fiddly plumbing, kept separate from the pipeline so it can't sink the centerpiece.
- [ ] Request notification permission; capture the device push token; store it.
- [ ] **Refresh the token on rotation** — stale tokens are the silent killer of push.
- [ ] Expo push send; handle iOS/Android; handle send failures (feeds the P4 failure dial).

### P6 — Taste-set expansion (Spotify)
Pure enrichment — *grows the set the scorer already consumes*, restructures nothing.
- [ ] Resolve each liked artist to a Spotify ID *(fuzzy match — see the mapping note;
      a miss here is a **soft** failure: you just don't get expansion for that artist)*.
- [ ] Pull **related artists** + genre tags; store an expanded "taste set" per user.
- [ ] Matching now lights up on adjacent artists (likes Radiohead → Thom Yorke, etc.).
- [ ] **Unlocks ranked genre discovery + artist recommendations** (both held until now):
      Spotify's `popularity` score and **taste-proximity** (related-to-what-you-like) give
      a *good* ranking — better than raw popularity — so genre-discovery recs and
      "artists you might like" can finally ship without feeling random.

### P7 — In-app chat ★ CENTERPIECE 2
Replaces the P3 compose-sheet hand-off button with a real system.
- [ ] WebSocket connection management, message persistence, fan-out, read state.
- [ ] Push-on-new-message (reuses P5 delivery).
- [ ] A thread per show, seeded with the friends who are going.
- **Built last on purpose:** its value is additive, not structural, so a time-crunch
  leaves a finished app + one centerpiece rather than two stubs.

---

## Backlog (deliberately deferred)

- **Identity & Discovery phase** — phone-number auth (SMS OTP + US A2P 10DLC
  registration), OAuth (**Sign in with Apple is App-Store-*required* if you offer
  Google**; watch "Hide My Email" relay addresses and cross-provider **identity
  unification**), and **contact-matching**. These move *together* — phone auth's entire
  payoff *is* contact-matching, so doing phone in isolation = all the cost, none of the
  benefit. Sequenced after the centerpieces because it's non-thesis plumbing carrying the
  project's nastiest correctness trap (identity unification).
- **Travel mode** — temporary location + date window ("I'll be in NYC in 3 weeks").
  Feasible (on-demand metro sync, cached, date-filtered) but it's a *solo-discovery*
  feature that goes dark on the social layer, and the per-favorite "anywhere" sync already
  covers the best of it. Defer.
- **Per-artist travel-willingness override** — "for *this* artist, Anywhere." Tier
  *defaults* ship now; the per-artist control is polish.
- **Per-artist taste hiding** — "hide this guilty-pleasure artist from friends."
- **Store-installable mobile build** (EAS/TestFlight).

### Ruled out (don't build toward these)
- **Auto-creating an iMessage group chat from the app — impossible.** iOS exposes no
  public API to create an iMessage chat or inject participants; the Messages framework
  only allows extensions/stickers *inside* Messages. The compose-sheet hand-off is the
  only legal near-term move; real coordination = in-app chat (P7).

---

## Locked design decisions (quick reference)

| Area | Decision |
|---|---|
| **Goal** | Live, deployed, impressive backend portfolio piece. Two finished centerpieces. |
| **Centerpieces** | (1) Notification pipeline, (2) in-app chat. Pipeline first. |
| **Build order** | Deploy now → P2 → P3 → **P3.5 UI pass** → pipeline → push (+ onboard friends) → Spotify → chat. |
| **Artist entry** | TM-first typeahead search, debounced + min-length, **write-through cached** into the local `artists` table. Spotify search not used (lossy mapping would feed *events* = hard fail). |
| **Genre entry** | Picker from TM taxonomy; pick at genre **or** sub-genre; **sub-genre match scores higher**; match hierarchically (a user's "Rock" matches rock sub-genres). |
| **Favorite vs liked** | The `user_artists.weight` tier. Triple duty: **travel scope + sync scope + match weight.** |
| **Event caches (two)** | Per-metro (scheduled, discovery) **+** per-favorite-artist (`attractionId`, "anywhere"). The second is cheap *because* the graph is closed (small favorites set). |
| **Travel willingness** | A metro-set **filter** (tiers: `Local`/`Regional`/`Anywhere`) over the everywhere-sync, computed from **metro centroids, never user GPS**. **Infra deferred to P4** (no anywhere-sync = no cross-metro events yet); the P3 scorer reserves the input slot. Per-artist override backlogged. |
| **Feed ranking (P3)** | One list: relevance score + **time-proximity boost** (~90-day decay). Chronological order is dead. |
| **Popularity (P3)** | TM attraction `upcomingEvents` count stored on `artists` at sync = proxy popularity term; **Spotify popularity swaps in at P6**, scorer shape unchanged. |
| **Taste-set (P3)** | Assembled **in-memory** from `user_artists`+`user_genres`; no `user_taste_artists` until P6, and then **`related` rows only** (no dual-write of explicit picks). |
| **Match display (P3)** | One strip: marked-going > marked-maybe > predicted. Two wording buckets ("would probably go" / "might be into this"); **no numeric scores or meters**. Symmetric; private interest never friend-visible. |
| **Social pull-in (P3)** | Feed inclusion = taste match **OR** ≥1 friend w/ shared going/maybe. |
| **Event search (P3)** | `GET /events/search` over **cached metro events** + feed search bar. Never live TM (typeahead stays the only per-user TM call). |
| **Compose sheet (P3)** | Trigger = **≥1 friend** with shared *marked* interest; predicted friends = suggested invitees only. Share text carries the TM link (`events.url`). |
| **Location** | Single `home_metro_id`. Geolocation → nearest DMA **once** at onboarding, then discarded; editable via picker. |
| **Discovery** | Invite-link / QR now; username search steady-state. Phone + contacts later (Identity & Discovery). |
| **Invites (P2)** | **Multi-use** token (cap ~25, ~7-day expiry, revocable), `invite_redemptions` audit table. Artifact = API **HTML landing page** + in-app code entry (no deep links pre-store-build). **Redeem = instant accepted friendship.** |
| **Usernames (P2)** | **Required at signup** (nullable for legacy); lowercase 3–20 `[a-z0-9_]`, unique. Search = **prefix, min 3 chars**, excludes self + blocked. |
| **Friendship lifecycle (P2)** | Decline / cancel / unfriend **delete the row** (re-requestable). **Block = silent full mutual severance**, requester = blocker, blocker-only unblock. |
| **Authz** | Taste + interest **friends-only** by default. **Private-interest flag** from day one. Match disclosure **symmetric**. |
| **TDD ramp** | Test-first where behavior is a spec: **P2 authz matrix test-first** (CRUD tests-after) → **P3 scorer strict TDD** → **P4 pipeline strict TDD** (idempotency/digest as failing tests first) → P7 chat logic TDD, WS plumbing manual. |
| **Pipeline** | Nightly per-metro diff → digest → `notifications_sent` ledger → **at-least-once w/ compensating claims**; **new-events-only** nightly, new-interest at add-time. |
| **Genre discovery / recs** | **Held until P6** — need Spotify popularity + taste-proximity to rank. Pre-P6 feed = high-confidence artist matches only (protect feed trust). |

---

## Schema (the parts annoying to change later)

```sql
-- Identity. Email auth for now; phone/OAuth land in the Identity & Discovery phase.
CREATE TABLE users (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              TEXT UNIQUE NOT NULL,
    display_name       TEXT NOT NULL,
    username           TEXT UNIQUE,           -- REQUIRED at signup (app-level) from P2 on;
                                              -- nullable only for legacy pre-P2 accounts.
                                              -- lowercase, 3–20 chars, [a-z0-9_]
    home_metro_id      TEXT,                  -- Ticketmaster DMA/market id
    location_precision TEXT NOT NULL DEFAULT 'metro'
                         CHECK (location_precision IN ('metro','city')),
    -- Travel-willingness tier DEFAULTS (per-artist override is backlog):
    travel_default_favorite TEXT NOT NULL DEFAULT 'regional'
                         CHECK (travel_default_favorite IN ('local','regional','anywhere')),
    travel_default_liked    TEXT NOT NULL DEFAULT 'local'
                         CHECK (travel_default_liked IN ('local','regional','anywhere')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reference table of metros, with centroids — powers travel-willingness as a
-- metro-set filter (metro-to-metro proximity), so user GPS is never matched on.
CREATE TABLE metros (
    metro_id    TEXT PRIMARY KEY,             -- Ticketmaster DMA/market id
    name        TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL
);

-- Canonical artists. Key by external id so you dedupe instead of free-texting names.
CREATE TABLE artists (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_attraction_id TEXT UNIQUE,             -- Ticketmaster attractionId
    spotify_id       TEXT UNIQUE,             -- filled in P6 (soft-fail if no match)
    name             TEXT NOT NULL,
    -- P3: touring-scale proxy for popularity (TM attraction upcomingEvents count,
    -- captured free during event sync). P6 replaces it with Spotify popularity.
    tm_upcoming_events SMALLINT
);

-- P3: TM genre taxonomy cache (classifications.json, fetched once). Powers the genre
-- picker + hierarchical matching (a user's "Rock" matches rock sub-genres).
CREATE TABLE tm_genres (
    tm_id        TEXT PRIMARY KEY,            -- TM classification id
    name         TEXT NOT NULL,
    parent_tm_id TEXT REFERENCES tm_genres(tm_id)  -- NULL = broad genre; set = sub-genre
);

-- Who likes whom. weight = the favorite/liked tier (favorite > liked).
CREATE TABLE user_artists (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    artist_id  UUID REFERENCES artists(id) ON DELETE CASCADE,
    weight     SMALLINT NOT NULL DEFAULT 1,   -- e.g. liked=1, favorite=2
    -- travel_override TEXT NULL  -- BACKLOG: per-artist willingness ('local'|'regional'|'anywhere')
    PRIMARY KEY (user_id, artist_id)
);

CREATE TABLE user_genres (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    genre      TEXT NOT NULL,                 -- from TM taxonomy (genre OR sub-genre)
    is_subgenre BOOLEAN NOT NULL DEFAULT false, -- sub-genre matches score higher
    PRIMARY KEY (user_id, genre)
);

-- Friendship: symmetric relationship, but the REQUEST is directional.
CREATE TABLE friendships (
    requester_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    addressee_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    status        TEXT NOT NULL CHECK (status IN ('pending','accepted','blocked')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (requester_id, addressee_id),
    CHECK (requester_id <> addressee_id)
);
-- One row per unordered pair (prevents A→B and B→A both existing):
CREATE UNIQUE INDEX friendship_pair_uniq
    ON friendships (LEAST(requester_id, addressee_id),
                    GREATEST(requester_id, addressee_id));

-- Invite links / QR (QR = this link rendered). MULTI-USE: one link serves the whole
-- group chat. Redeeming creates an instant 'accepted' friendship with the inviter.
CREATE TABLE invites (
    token       TEXT PRIMARY KEY,
    inviter_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    max_uses    SMALLINT NOT NULL DEFAULT 25,
    expires_at  TIMESTAMPTZ NOT NULL,          -- default now() + 7 days
    revoked_at  TIMESTAMPTZ,                   -- soft revoke; keeps the audit trail
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE invite_redemptions (
    token       TEXT REFERENCES invites(token) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    redeemed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (token, user_id)
);

-- Events cached from the API, keyed by external id. metro_id may be OUTSIDE the user's
-- home metro (per-favorite "anywhere" sync) — travel-willingness filters at read time.
CREATE TABLE events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tm_event_id  TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    artist_id    UUID REFERENCES artists(id),
    venue_name   TEXT,
    metro_id     TEXT,
    starts_at    TIMESTAMPTZ,
    genre        TEXT,
    subgenre     TEXT,                        -- P3: TM subGenre (sub-genre match scores higher)
    url          TEXT,                        -- P3: TM event link (compose-sheet share text)
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User marks interest. Powers both matching and notifications.
CREATE TABLE event_interest (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    event_id   UUID REFERENCES events(id) ON DELETE CASCADE,
    level      TEXT NOT NULL CHECK (level IN ('going','maybe')),
    -- private interest still feeds YOUR notifications/feed, but is hidden from friends
    -- and excluded from the match results friends see about you:
    visibility TEXT NOT NULL DEFAULT 'shared' CHECK (visibility IN ('shared','private')),
    PRIMARY KEY (user_id, event_id)
);

-- P6 ONLY: Spotify-derived adjacent artists ('related' rows exclusively — explicit
-- picks stay in user_artists, never mirrored here; the taste-set assembler unions the
-- two at read time). Locked P3 decision: no dual-write of explicit taste.
CREATE TABLE user_taste_artists (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    artist_id  UUID REFERENCES artists(id) ON DELETE CASCADE,
    source     TEXT NOT NULL CHECK (source = 'related'),
    score      REAL NOT NULL DEFAULT 1.0,
    PRIMARY KEY (user_id, artist_id)
);

-- P4: idempotency ledger so the pipeline never double-notifies. Claimed with
-- ON CONFLICT DO NOTHING; committed after the push succeeds (at-least-once).
CREATE TABLE notifications_sent (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    event_id   UUID REFERENCES events(id) ON DELETE CASCADE,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);

-- P5: push tokens. Refresh on rotation or notifications silently die.
CREATE TABLE device_tokens (
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL,
    platform    TEXT NOT NULL CHECK (platform IN ('ios','android')),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (token)
);

-- P7: in-app chat (one thread per show).
CREATE TABLE chat_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id    UUID REFERENCES events(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id   UUID REFERENCES chat_threads(id) ON DELETE CASCADE,
    sender_id   UUID REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> Schema beyond P2 (`user_taste_artists` source semantics, `notifications_sent`,
> `device_tokens`, chat tables, travel columns) is sketched so the *annoying-to-change*
> shapes are decided now; build the columns/tables when their phase lands.

---

## Ticketmaster Discovery API — endpoints you'll actually hit

Base: `https://app.ticketmaster.com/discovery/v2/`  (pass `apikey=` on every call)

- **Per-metro music events** (scheduled cache job — discovery feed):
  `events.json?classificationName=music&dmaId={DMA}&apikey=...`
- **Per-favorite-artist events, anywhere** (scheduled, the second cache):
  `events.json?attractionId={id}&apikey=...`
- **Artist typeahead search** (the one allowed per-user TM call — debounce, min-length,
  write-through cache): `attractions.json?keyword={name}&apikey=...`
- **Genre taxonomy** (fetch once, cache; powers the genre picker):
  `classifications.json?apikey=...`
- Watch the `Rate-Limit-Available` response header; back off at 429.

Spotify (P6): artist search + **related artists** endpoints build the expanded taste set
and provide `popularity` for ranked discovery. Resolve names → Spotify IDs once and store
on the `artists` row.

---

## The hard spots (brace for these)

**Notification pipeline (P4 — centerpiece 1).** The three traps *are* the learning:
idempotency (the ledger; don't double-notify), deduplication (one digest, not five pings),
rate-sanity (per-metro pulls, cache hard). The deliberate call is the **failure dial**:
**at-least-once with compensating claims**, because a missed concert alert is worse than a
duplicate.

**In-app chat (P7 — centerpiece 2).** Real-time = WebSocket connection management, message
persistence, fan-out, read state, push-on-new-message. Built last so it can't starve the
pipeline; the P3 compose-sheet button is the seam it slots into.

**Artist ↔ Spotify mapping (P6).** Spotify and Ticketmaster share no common id, so mapping
is **fuzzy name matching** (ambiguity, normalization, coverage gaps) — a quiet
entity-resolution subsystem. It's deliberately placed on *enrichment* (P6), where a miss is
a **soft** failure (no expansion for one artist), **never** on events, where a miss would
**break the core feed**. That asymmetry is *why* artist search is TM-first.

---

## Mobile gotchas checklist

- [ ] **Request notification permission**, capture the device push token, store it, and
      **refresh it on rotation** (P5). Stale tokens silently kill push.
- [ ] **Never trust the client for matching.** All scoring + fan-out server-side.
- [ ] **Token-based auth** with secure on-device storage. No session cookies.
- [ ] **Match on metro, never raw coordinates.** Resolve geolocation → metro once, discard.
- [ ] **Keep the pre-P6 feed to high-confidence artist matches** — don't ship random-feeling
      genre discovery and burn feed trust before Spotify can rank it.

---

## Testing

- **Phase 1 test plan:** `docs/PHASE-1-TEST-PLAN.md` — full end-to-end checklist for the
  single-user feed (auth, taste entry, event sync, feed, mobile). Read it before testing
  P1. Key gotcha: with no Ticketmaster API key the app runs in **stub mode**, where genre
  matching is testable but artist matching is not.
- **TDD ramp (locked 2026-07-01):** test-first where the behavior is a spec, tests-after
  for plumbing. **P2:** authz matrix test-first (pytest + httpx, first automated suite),
  CRUD tests-after, manual mobile checklist in `docs/PHASE-2-TEST-PLAN.md`. **P3:** strict
  TDD on the match scorer (pure function). **P4:** strict TDD on the pipeline —
  "run twice → sends nothing" and "N events → 1 digest" exist as failing tests before the
  pipeline code. **P7:** TDD chat persistence/read-state; WebSocket plumbing manual.
- **Active virtualenv is `.venv/` at the repo root** (`.venv/Scripts/python.exe`), not
  `backend/venv/`.

> A working simple version you can show beats an ambitious half-built one in every
> interview — so the core loop (through P3) is shippable on its own, and the two
> centerpieces are upgrades layered on a thing that already works.
