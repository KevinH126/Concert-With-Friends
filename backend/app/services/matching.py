"""P3 match scorer — one pure function used everywhere (feed ranking, friend
prediction, digest relevance). All weights/thresholds are named tunable
constants; the TDD suite pins their *ordering*, never their values.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventInterest, TmGenre, UserArtist, UserGenre


@dataclass(frozen=True)
class TasteSet:
    favorite_artist_ids: frozenset[str]
    liked_artist_ids: frozenset[str]
    history_going_artist_ids: frozenset[str]
    history_maybe_artist_ids: frozenset[str]
    genres: frozenset[str]
    history_genres: frozenset[str]


@dataclass(frozen=True)
class EventFacts:
    artist_id: str | None
    genre: str | None
    subgenre: str | None
    artist_popularity: int
    starts_at: datetime | None


@dataclass(frozen=True)
class ScoringCtx:
    now: datetime
    genre_parents: Mapping[str, str]
    friends_going: int
    friends_maybe: int
    own_interest: str | None
    in_range: bool = True  # reserved travel slot — constant no-op in P3


@dataclass(frozen=True)
class MatchReason:
    """The single strongest taste signal behind a match — what the UI names on the
    prediction strip. `kind` drives the client copy + icon:
      'favorite_artist' — the event's artist is one of their favorites (strong),
      'artist'          — a liked artist or one revealed by their mark history,
      'genre'           — any genre/sub-genre/sibling/history-genre match.
    `genre` carries the matched genre name for kind == 'genre'; None for artists
    (the client already has the event's artist name)."""
    kind: str
    genre: str | None = None


# Artist tiers: explicit picks beat revealed history; a committed mark beats a hesitant one.
W_ARTIST_FAVORITE = 100.0
W_ARTIST_LIKED = 60.0
W_ARTIST_HISTORY_GOING = 40.0
W_ARTIST_HISTORY_MAYBE = 20.0

# Genre tiers: picking the exact sub-genre is a sharper statement than the broad genre.
# A broad pick still matches any of its sub-genres (hierarchical, via ctx.genre_parents).
W_GENRE_SUBGENRE = 30.0
W_GENRE_BROAD = 18.0
# A picked sub-genre also surfaces its siblings (other sub-genres of the same broad
# genre), but weaker than an exact hit and weaker than picking the broad genre
# outright — a narrower pick must not out-pull the same show for a broad-genre fan.
W_GENRE_SUBGENRE_SIBLING = 12.0
W_GENRE_HISTORY = 10.0  # genre inferred from marks — implicit, below any explicit pick

# Popularity (TM upcomingEvents proxy; Spotify swaps in at P6): a bounded tiebreaker
# among taste matches, never a reason to show a card on its own.
W_POPULARITY_MAX = 15.0
POPULARITY_CEILING = 50  # upcoming-events count at which the bonus saturates

# Social terms. Unlike popularity, friend interest stands on its own (social pull-in:
# a friend's real interest is reason enough to surface a card with zero taste overlap).
W_FRIEND_GOING = 25.0
W_FRIEND_MAYBE = 12.0
W_OWN_GOING = 30.0
W_OWN_MAYBE = 15.0

# Time proximity: a modest multiplier so sooner wins among comparable matches while a
# favorite artist months out still tops the list. Unknown dates get no boost.
TIME_BOOST_MAX = 0.25  # at most +25%, fully decayed by TIME_DECAY_DAYS out
TIME_DECAY_DAYS = 90.0

# Friend-prediction wording buckets. Hand-tuned v1 weights don't earn numeric display —
# the client only ever sees the bucket ('probably' / 'might' / hidden).
BUCKET_PROBABLY_MIN = 80.0
BUCKET_MIGHT_MIN = 25.0


# The reason helpers are the single source of truth for the taste tiers: each
# returns (weight, reason) for its strongest match, and the _term wrappers below
# expose just the weight to score(). This keeps ranking and explanation in lockstep.
def _artist_reason(taste: TasteSet, event: EventFacts) -> tuple[float, MatchReason] | None:
    if event.artist_id is None:
        return None
    if event.artist_id in taste.favorite_artist_ids:
        return W_ARTIST_FAVORITE, MatchReason("favorite_artist")
    if event.artist_id in taste.liked_artist_ids:
        return W_ARTIST_LIKED, MatchReason("artist")
    if event.artist_id in taste.history_going_artist_ids:
        return W_ARTIST_HISTORY_GOING, MatchReason("artist")
    if event.artist_id in taste.history_maybe_artist_ids:
        return W_ARTIST_HISTORY_MAYBE, MatchReason("artist")
    return None


def _genre_reason(taste: TasteSet, event: EventFacts, ctx: ScoringCtx) -> tuple[float, MatchReason] | None:
    best: tuple[float, MatchReason] | None = None

    def consider(weight: float, name: str) -> None:
        nonlocal best
        if best is None or weight > best[0]:
            best = (weight, MatchReason("genre", name))

    event_parent = ctx.genre_parents.get(event.subgenre) if event.subgenre is not None else None
    if event.subgenre is not None:
        if event.subgenre in taste.genres:
            consider(W_GENRE_SUBGENRE, event.subgenre)
        if event_parent is not None and event_parent in taste.genres:
            consider(W_GENRE_BROAD, event_parent)
    if event.genre is not None and event.genre in taste.genres:
        consider(W_GENRE_BROAD, event.genre)

    # Sibling reach: a picked sub-genre also surfaces other shows under the same
    # broad genre. The event's broad genre is its own `genre` and/or its sub-genre's
    # parent; any picked sub-genre sharing that parent is a (weaker) sibling match.
    event_broad = {g for g in (event.genre, event_parent) if g is not None}
    if event_broad:
        for picked in taste.genres:
            parent = ctx.genre_parents.get(picked)
            if parent in event_broad:
                consider(W_GENRE_SUBGENRE_SIBLING, parent)
                break

    for name in (event.genre, event.subgenre):
        if name is not None and name in taste.history_genres:
            consider(W_GENRE_HISTORY, name)
    return best


def _artist_term(taste: TasteSet, event: EventFacts) -> float:
    r = _artist_reason(taste, event)
    return r[0] if r else 0.0


def _genre_term(taste: TasteSet, event: EventFacts, ctx: ScoringCtx) -> float:
    r = _genre_reason(taste, event, ctx)
    return r[0] if r else 0.0


def explain_match(taste: TasteSet, event: EventFacts, ctx: ScoringCtx) -> MatchReason | None:
    """The dominant taste signal behind the match — the single largest base term,
    mirroring score()'s tiering. None when nothing in taste matches (base == 0)."""
    candidates = [
        r for r in (_artist_reason(taste, event), _genre_reason(taste, event, ctx)) if r is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def _popularity_term(event: EventFacts) -> float:
    saturation = min(event.artist_popularity, POPULARITY_CEILING) / POPULARITY_CEILING
    return W_POPULARITY_MAX * saturation


def _social_term(ctx: ScoringCtx) -> float:
    total = ctx.friends_going * W_FRIEND_GOING + ctx.friends_maybe * W_FRIEND_MAYBE
    if ctx.own_interest == "going":
        total += W_OWN_GOING
    elif ctx.own_interest == "maybe":
        total += W_OWN_MAYBE
    return total


def _time_multiplier(event: EventFacts, ctx: ScoringCtx) -> float:
    if event.starts_at is None:
        return 1.0
    days_until = (event.starts_at - ctx.now).total_seconds() / 86400
    closeness = min(1.0, max(0.0, 1.0 - days_until / TIME_DECAY_DAYS))
    return 1.0 + TIME_BOOST_MAX * closeness


def score(taste: TasteSet, event: EventFacts, ctx: ScoringCtx) -> float:
    base = _artist_term(taste, event) + _genre_term(taste, event, ctx)
    if base > 0:
        base += _popularity_term(event)
    return (base + _social_term(ctx)) * _time_multiplier(event, ctx)


# user_artists.weight tier boundary: >= this is a favorite, below is liked.
FAVORITE_WEIGHT_MIN = 2


async def load_genre_parents(db: AsyncSession) -> dict[str, str]:
    """subgenre-name -> parent-genre-name from the tm_genres cache, for ScoringCtx.
    Empty until POST /admin/sync-genres has run (scorer degrades to exact matches)."""
    rows = await db.execute(select(TmGenre))
    genres = rows.scalars().all()
    names = {g.tm_id: g.name for g in genres}
    return {
        g.name: names[g.parent_tm_id]
        for g in genres
        # Skip TM's same-named subgenres — a "Rock"→"Rock" mapping is meaningless
        # (exact match already covers it) and would shadow real entries.
        if g.parent_tm_id is not None
        and g.parent_tm_id in names
        and g.name != names[g.parent_tm_id]
    }


async def assemble_taste_set(db: AsyncSession, user_id: str, *, friend_visible: bool) -> TasteSet:
    """Build a user's TasteSet in-memory at request time (no storage — a signature
    promise). friend_visible=True is the variant fed into predictions other users
    see; it must never learn from private marks."""
    artist_rows = await db.execute(
        select(UserArtist.artist_id, UserArtist.weight).where(UserArtist.user_id == user_id)
    )
    favorites, liked = set(), set()
    for artist_id, weight in artist_rows.all():
        (favorites if weight >= FAVORITE_WEIGHT_MIN else liked).add(artist_id)

    genre_rows = await db.execute(select(UserGenre.genre).where(UserGenre.user_id == user_id))
    genres = {row[0] for row in genre_rows.all()}

    history_query = (
        select(EventInterest.level, Event.artist_id, Event.genre)
        .join(Event, Event.id == EventInterest.event_id)
        .where(EventInterest.user_id == user_id)
    )
    if friend_visible:
        history_query = history_query.where(EventInterest.visibility == "shared")
    history_rows = await db.execute(history_query)
    history_going, history_maybe, history_genres = set(), set(), set()
    for level, artist_id, genre in history_rows.all():
        if artist_id is not None:
            (history_going if level == "going" else history_maybe).add(artist_id)
        if genre is not None:
            history_genres.add(genre)

    return TasteSet(
        favorite_artist_ids=frozenset(favorites),
        liked_artist_ids=frozenset(liked),
        history_going_artist_ids=frozenset(history_going),
        history_maybe_artist_ids=frozenset(history_maybe),
        genres=frozenset(genres),
        history_genres=frozenset(history_genres),
    )


def prediction_bucket(value: float) -> str | None:
    """Map a friend's score to the wording bucket shown on the strip, or None to hide."""
    if value >= BUCKET_PROBABLY_MIN:
        return "probably"
    if value >= BUCKET_MIGHT_MIN:
        return "might"
    return None
