"""P3 genre subsystem: taxonomy cache, picker validation, sync-captured fields."""
from app.models import TmGenre
from app.services.event_sync import sync_genres
from app.services.matching import load_genre_parents
from app.services.ticketmaster import parse_tm_event
from tests.conftest import create_user


async def seed_taxonomy(db_session):
    db_session.add(TmGenre(tm_id="G_ROCK", name="Rock", parent_tm_id=None))
    db_session.add(TmGenre(tm_id="SG_INDIE", name="Indie Rock", parent_tm_id="G_ROCK"))
    # TM's real taxonomy has a same-named subgenre under nearly every broad genre
    # (genre "Rock" → subgenre "Rock") — regression fodder for the 500 this caused.
    db_session.add(TmGenre(tm_id="SG_ROCK_DUP", name="Rock", parent_tm_id="G_ROCK"))
    db_session.add(TmGenre(tm_id="G_JAZZ", name="Jazz", parent_tm_id=None))
    await db_session.commit()


class TestParseTmEvent:
    def test_extracts_subgenre_url_and_popularity(self):
        raw = {
            "id": "EVT1",
            "name": "Show",
            "url": "https://tm.test/show",
            "dates": {"start": {"dateTime": "2026-08-15T20:00:00Z"}},
            "_embedded": {
                "attractions": [{"id": "ATT1", "name": "Band", "upcomingEvents": {"_total": 12}}],
                "venues": [{"name": "Venue"}],
            },
            "classifications": [{"genre": {"name": "Rock"}, "subGenre": {"name": "Indie Rock"}}],
        }
        parsed = parse_tm_event(raw, "345")
        assert parsed["subgenre"] == "Indie Rock"
        assert parsed["url"] == "https://tm.test/show"
        assert parsed["tm_upcoming_events"] == 12

    def test_missing_fields_parse_as_none(self):
        raw = {"id": "EVT2", "name": "Bare Show"}
        parsed = parse_tm_event(raw, "345")
        assert parsed["subgenre"] is None
        assert parsed["url"] is None
        assert parsed["tm_upcoming_events"] is None


class TestGenreSync:
    async def test_sync_genres_is_idempotent(self, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlalchemy import select

        maker = async_sessionmaker(db_engine, expire_on_commit=False)
        first = await sync_genres(session_factory=maker)   # stub taxonomy (no API key)
        second = await sync_genres(session_factory=maker)  # re-run must not duplicate
        assert first == second > 0

        async with maker() as db:
            rows = (await db.execute(select(TmGenre))).scalars().all()
        assert len(rows) == first


class TestGenrePicker:
    async def test_taxonomy_groups_subgenres_under_parents(self, client, db_session):
        await seed_taxonomy(db_session)
        _, headers = await create_user(client, "pickeruser")

        resp = await client.get("/genres/taxonomy", headers=headers)
        assert resp.status_code == 200
        taxonomy = {g["name"]: g["subgenres"] for g in resp.json()}
        assert taxonomy == {"Rock": ["Indie Rock"], "Jazz": []}

    async def test_add_genre_from_taxonomy_records_subgenre_flag(self, client, db_session):
        await seed_taxonomy(db_session)
        _, headers = await create_user(client, "subgenreuser")

        resp = await client.post("/genres", json={"genre": "Indie Rock"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json() == ["Indie Rock"]

    async def test_ambiguous_name_prefers_broad_genre(self, client, db_session):
        """TM has genre 'Rock' AND subgenre 'Rock' — picking 'Rock' must resolve to
        the broad genre (hierarchical match, wider net), never 500 on ambiguity."""
        await seed_taxonomy(db_session)
        user_id, headers = await create_user(client, "ambiguoususer")

        resp = await client.post("/genres", json={"genre": "Rock"}, headers=headers)
        assert resp.status_code == 201

        from sqlalchemy import select
        from app.models import UserGenre
        row = (await db_session.execute(
            select(UserGenre).where(UserGenre.user_id == user_id)
        )).scalar_one()
        assert row.is_subgenre is False

    async def test_taxonomy_hides_same_named_subgenres(self, client, db_session):
        await seed_taxonomy(db_session)
        _, headers = await create_user(client, "dedupeuser")

        resp = await client.get("/genres/taxonomy", headers=headers)
        taxonomy = {g["name"]: g["subgenres"] for g in resp.json()}
        assert taxonomy["Rock"] == ["Indie Rock"]  # the duplicate "Rock" sub is noise

    async def test_free_text_genre_is_rejected(self, client, db_session):
        await seed_taxonomy(db_session)
        _, headers = await create_user(client, "freetextuser")

        resp = await client.post("/genres", json={"genre": "rock"}, headers=headers)  # wrong case
        assert resp.status_code == 422
        resp = await client.post("/genres", json={"genre": "Vaporwave"}, headers=headers)
        assert resp.status_code == 422


class TestGenreParents:
    async def test_loads_subgenre_to_parent_name_mapping(self, db_session):
        await seed_taxonomy(db_session)
        parents = await load_genre_parents(db_session)
        assert parents == {"Indie Rock": "Rock"}
