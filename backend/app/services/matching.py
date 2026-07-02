"""P3 match scorer — one pure function used everywhere (feed ranking, friend
prediction, digest relevance). All weights/thresholds are named tunable
constants; the TDD suite pins their *ordering*, never their values.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


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


# Artist tiers: explicit picks beat revealed history; a committed mark beats a hesitant one.
W_ARTIST_FAVORITE = 100.0
W_ARTIST_LIKED = 60.0
W_ARTIST_HISTORY_GOING = 40.0
W_ARTIST_HISTORY_MAYBE = 20.0

# Genre tiers: picking the exact sub-genre is a sharper statement than the broad genre.
# A broad pick still matches any of its sub-genres (hierarchical, via ctx.genre_parents).
W_GENRE_SUBGENRE = 30.0
W_GENRE_BROAD = 18.0
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


def _artist_term(taste: TasteSet, event: EventFacts) -> float:
    if event.artist_id is None:
        return 0.0
    if event.artist_id in taste.favorite_artist_ids:
        return W_ARTIST_FAVORITE
    if event.artist_id in taste.liked_artist_ids:
        return W_ARTIST_LIKED
    if event.artist_id in taste.history_going_artist_ids:
        return W_ARTIST_HISTORY_GOING
    if event.artist_id in taste.history_maybe_artist_ids:
        return W_ARTIST_HISTORY_MAYBE
    return 0.0


def _genre_term(taste: TasteSet, event: EventFacts, ctx: ScoringCtx) -> float:
    best = 0.0
    if event.subgenre is not None:
        if event.subgenre in taste.genres:
            best = max(best, W_GENRE_SUBGENRE)
        if ctx.genre_parents.get(event.subgenre) in taste.genres:
            best = max(best, W_GENRE_BROAD)
    if event.genre is not None and event.genre in taste.genres:
        best = max(best, W_GENRE_BROAD)
    for name in (event.genre, event.subgenre):
        if name is not None and name in taste.history_genres:
            best = max(best, W_GENRE_HISTORY)
    return best


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


def prediction_bucket(value: float) -> str | None:
    """Map a friend's score to the wording bucket shown on the strip, or None to hide."""
    if value >= BUCKET_PROBABLY_MIN:
        return "probably"
    if value >= BUCKET_MIGHT_MIN:
        return "might"
    return None
