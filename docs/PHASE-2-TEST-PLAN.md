# Phase 2 test plan — social graph + interest-marking

The authz matrix and friendship state machine are covered by the automated suite
(`backend/tests/` — run `python -m pytest` from `backend/` with the repo-root venv;
local Docker Postgres must be up). **This checklist covers what the suite can't: the
mobile flows, on two real devices/accounts.**

Backend prereqs: P2 migration applied (`alembic upgrade head`), events seeded for
your test metro (`POST /admin/sync/{metro_id}`).

Suggested cast: **A = you (legacy account, no username yet)**, **B = a fresh signup.**

## 1. Usernames

- [ ] Sign up as B **without** a username → blocked client-side; API also rejects it.
- [ ] Sign up as B with username `Test_User` → rejected (uppercase); `tb` → rejected
      (too short); valid lowercase one → succeeds.
- [ ] Log in as A (pre-P2 account) → Profile tab shows no @username; set one; it
      sticks after re-login.
- [ ] A tries to take B's username → "That username is taken."

## 2. Invites (the bootstrap path)

- [ ] A: Friends tab → **Invite friends** → modal shows QR + code; **Share link**
      opens the OS share sheet.
- [ ] Open the shared link in a phone browser → landing page shows A's name + the code.
- [ ] Scan the QR with the other phone's camera → same landing page.
- [ ] B: **Enter invite code** → paste the *full URL* → "Friend added!"; A and B now
      appear in each other's Friends lists **with no accept step**.
- [ ] B redeems the same code again → friendly "no longer valid / already friends"
      behavior (no crash, no duplicate friend row).
- [ ] A redeems own code → "You can't redeem your own invite."

## 3. Requests via search

- [ ] (Unfriend first, from a profile screen.) B: search 2 letters → no results;
      3+ letters of A's username → A appears with **Add**.
- [ ] B taps Add → A's Friends tab shows the request under **Friend requests**;
      B sees it under **Sent requests** with **Cancel**.
- [ ] A declines → both lists clear; B can Add again (clean slate).
- [ ] A accepts the re-request → both see each other under Friends.

## 4. Friend profile + taste authz

- [ ] A: tap B in Friends → profile shows B's favorite/liked artists, genres, and
      upcoming interested events. No email shown anywhere.
- [ ] B's *private* interests do not appear (see §5).

## 5. Interest-marking + privacy

- [ ] B: Feed → tap **Going** on an event → button fills; A's feed for the same
      event shows "**B is going**" strip; A's view of B's profile lists the event.
- [ ] B: **long-press** Maybe on a second event → shows 🔒; that event does **not**
      appear on A's feed strip or in B's profile as seen by A — but B still sees it
      in their own feed as marked.
- [ ] B: tap the active button again → interest cleared everywhere.

## 6. Block

- [ ] A: B's profile → **Block** (confirm dialog warns; B is not notified).
- [ ] Both: friends lists empty; neither appears in the other's search results; the
      event strips stop showing each other.
- [ ] B: tries to redeem one of A's old invite codes → generic "doesn't exist" error.
- [ ] (Unblock currently has no UI — clean up via API if needed:
      `DELETE /friends/{user_id}/block` as the blocker.)

## 7. Regression sweep (P1 still works)

- [ ] Feed loads and matches taste; Going/Maybe still toggles; Taste tab add/remove
      still works; sign out/in works.
