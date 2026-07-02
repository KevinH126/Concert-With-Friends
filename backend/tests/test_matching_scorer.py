"""P3 match scorer — strict TDD suite.

Pins the *behavioral contract* of score(taste, event, ctx): tier ordering,
hierarchy, and term interactions. Never reads the constants themselves —
weights are tunable; the ordering is the spec.
"""
from datetime import datetime, timedelta, timezone

from app.services.matching import (
    EventFacts,
    ScoringCtx,
    TasteSet,
    prediction_bucket,
    score,
)

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
SOON = NOW + timedelta(days=30)


def taste(**overrides) -> TasteSet:
    base = dict(
        favorite_artist_ids=frozenset(),
        liked_artist_ids=frozenset(),
        history_going_artist_ids=frozenset(),
        history_maybe_artist_ids=frozenset(),
        genres=frozenset(),
        history_genres=frozenset(),
    )
    base.update(overrides)
    return TasteSet(**base)


def event(**overrides) -> EventFacts:
    base = dict(
        artist_id="artist-1",
        genre=None,
        subgenre=None,
        artist_popularity=0,
        starts_at=SOON,
    )
    base.update(overrides)
    return EventFacts(**base)


def ctx(**overrides) -> ScoringCtx:
    base = dict(
        now=NOW,
        genre_parents={},
        friends_going=0,
        friends_maybe=0,
        own_interest=None,
    )
    base.update(overrides)
    return ScoringCtx(**base)


class TestArtistTiers:
    def test_favorite_artist_outranks_liked_artist(self):
        favorite = score(taste(favorite_artist_ids=frozenset({"artist-1"})), event(), ctx())
        liked = score(taste(liked_artist_ids=frozenset({"artist-1"})), event(), ctx())
        assert favorite > liked

    def test_liked_artist_outranks_no_match(self):
        liked = score(taste(liked_artist_ids=frozenset({"artist-1"})), event(), ctx())
        nothing = score(taste(), event(), ctx())
        assert liked > nothing


class TestGenreHierarchy:
    ROCK_TREE = {"Indie Rock": "Rock"}

    def test_subgenre_pick_outranks_broad_pick(self):
        rock_event = event(genre="Rock", subgenre="Indie Rock")
        sub = score(
            taste(genres=frozenset({"Indie Rock"})), rock_event, ctx(genre_parents=self.ROCK_TREE)
        )
        broad = score(
            taste(genres=frozenset({"Rock"})), rock_event, ctx(genre_parents=self.ROCK_TREE)
        )
        assert sub > broad > 0

    def test_broad_pick_matches_event_subgenre_via_parent(self):
        # User picked "Rock"; event only carries subgenre "Indie Rock" (parent: Rock).
        rock_event = event(genre=None, subgenre="Indie Rock")
        broad = score(
            taste(genres=frozenset({"Rock"})), rock_event, ctx(genre_parents=self.ROCK_TREE)
        )
        assert broad > 0

    def test_unrelated_genre_scores_nothing(self):
        country_fan = taste(genres=frozenset({"Country"}))
        rock_event = event(genre="Rock", subgenre="Indie Rock")
        assert score(country_fan, rock_event, ctx(genre_parents=self.ROCK_TREE)) == 0


class TestInterestHistoryTiers:
    """Revealed preference: marks teach the scorer, at implicit weight.
    Locked ordering: favorite > liked > history-going > history-maybe."""

    def test_going_history_outranks_maybe_history(self):
        going = score(taste(history_going_artist_ids=frozenset({"artist-1"})), event(), ctx())
        maybe = score(taste(history_maybe_artist_ids=frozenset({"artist-1"})), event(), ctx())
        assert going > maybe > 0

    def test_explicit_liked_outranks_going_history(self):
        liked = score(taste(liked_artist_ids=frozenset({"artist-1"})), event(), ctx())
        going = score(taste(history_going_artist_ids=frozenset({"artist-1"})), event(), ctx())
        assert liked > going

    def test_history_genre_counts_below_explicit_genre(self):
        rock_event = event(genre="Rock")
        explicit = score(taste(genres=frozenset({"Rock"})), rock_event, ctx())
        implicit = score(taste(history_genres=frozenset({"Rock"})), rock_event, ctx())
        assert explicit > implicit > 0


class TestPopularity:
    """TM upcomingEvents proxy: sinks cafe bands below touring acts among equal
    matches, but taste always beats fame."""

    def test_popularity_separates_equal_genre_matches(self):
        rock_fan = taste(genres=frozenset({"Rock"}))
        touring_act = event(artist_id="big", genre="Rock", artist_popularity=40)
        cafe_band = event(artist_id="small", genre="Rock", artist_popularity=1)
        assert score(rock_fan, touring_act, ctx()) > score(rock_fan, cafe_band, ctx())

    def test_popularity_never_outranks_direct_artist_match(self):
        fan = taste(liked_artist_ids=frozenset({"my-band"}))
        my_show = event(artist_id="my-band", artist_popularity=0)
        megastar = event(artist_id="stranger", genre=None, artist_popularity=10_000)
        assert score(fan, my_show, ctx()) > score(fan, megastar, ctx())

    def test_popularity_alone_scores_nothing(self):
        # No taste overlap at all: fame is a tiebreaker, not a reason to show a card.
        assert score(taste(), event(artist_popularity=10_000), ctx()) == 0


class TestSocialTerms:
    def test_friend_going_boosts_score(self):
        rock_fan = taste(genres=frozenset({"Rock"}))
        rock_event = event(genre="Rock")
        with_friend = score(rock_fan, rock_event, ctx(friends_going=1))
        alone = score(rock_fan, rock_event, ctx())
        assert with_friend > alone

    def test_friend_going_outranks_friend_maybe(self):
        going = score(taste(), event(), ctx(friends_going=1))
        maybe = score(taste(), event(), ctx(friends_maybe=1))
        assert going > maybe

    def test_friend_interest_alone_scores_positive(self):
        # Social pull-in: a friend's real interest beats a genre match as a reason
        # to surface a card — it must score even with zero taste overlap.
        assert score(taste(), event(), ctx(friends_going=1)) > 0

    def test_own_interest_boosts_going_over_maybe_over_none(self):
        rock_fan = taste(genres=frozenset({"Rock"}))
        rock_event = event(genre="Rock")
        going = score(rock_fan, rock_event, ctx(own_interest="going"))
        maybe = score(rock_fan, rock_event, ctx(own_interest="maybe"))
        none = score(rock_fan, rock_event, ctx())
        assert going > maybe > none


class TestTimeProximity:
    def test_among_equal_matches_sooner_wins(self):
        rock_fan = taste(genres=frozenset({"Rock"}))
        next_week = event(genre="Rock", starts_at=NOW + timedelta(days=7))
        in_two_months = event(genre="Rock", starts_at=NOW + timedelta(days=60))
        assert score(rock_fan, next_week, ctx()) > score(rock_fan, in_two_months, ctx())

    def test_favorite_months_out_still_beats_genre_match_next_week(self):
        # The boost is a modest multiplier: it reorders comparable matches,
        # never lets a weak match leapfrog a favorite artist.
        fan = taste(favorite_artist_ids=frozenset({"artist-1"}), genres=frozenset({"Rock"}))
        favorite_far = event(artist_id="artist-1", starts_at=NOW + timedelta(days=120))
        genre_soon = event(artist_id="other", genre="Rock", starts_at=NOW + timedelta(days=7))
        assert score(fan, favorite_far, ctx()) > score(fan, genre_soon, ctx())

    def test_unknown_date_gets_no_boost_and_no_crash(self):
        rock_fan = taste(genres=frozenset({"Rock"}))
        undated = event(genre="Rock", starts_at=None)
        dated_soon = event(genre="Rock", starts_at=NOW + timedelta(days=7))
        assert 0 < score(rock_fan, undated, ctx()) < score(rock_fan, dated_soon, ctx())


class TestReservedTravelSlot:
    def test_in_range_is_a_noop_in_p3(self):
        # The signature reserves the travel input; infra lands with P4. Until then
        # it must not move a score — this test is deleted when travel goes live.
        fan = taste(favorite_artist_ids=frozenset({"artist-1"}))
        assert score(fan, event(), ctx(in_range=True)) == score(fan, event(), ctx(in_range=False))


class TestPredictionBuckets:
    """Two wording buckets ride the API ('would probably go' / 'might be into
    this'); weak predictions are hidden. No numbers ever reach the client."""

    def test_favorite_artist_predicts_probably(self):
        s = score(taste(favorite_artist_ids=frozenset({"artist-1"})), event(), ctx())
        assert prediction_bucket(s) == "probably"

    def test_liked_artist_predicts_might(self):
        s = score(taste(liked_artist_ids=frozenset({"artist-1"})), event(), ctx())
        assert prediction_bucket(s) == "might"

    def test_broad_genre_alone_is_hidden(self):
        s = score(taste(genres=frozenset({"Rock"})), event(genre="Rock", artist_popularity=0), ctx())
        assert prediction_bucket(s) is None

    def test_zero_score_is_hidden(self):
        assert prediction_bucket(0.0) is None
