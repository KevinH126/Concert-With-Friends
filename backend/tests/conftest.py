"""Test fixtures: real local Postgres (schema is PG-specific), per-test clean schema.

The DATABASE_URL override MUST happen before any `app.*` import, because
`app.config.settings` is instantiated at import time.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/concert_friends_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ["TICKETMASTER_API_KEY"] = ""  # force stub mode; tests never call TM

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Artist, Event, UserGenre


def pytest_configure(config):
    """Create the test database if it doesn't exist yet."""
    url = make_url(TEST_DATABASE_URL)
    conn = psycopg2.connect(
        dbname="postgres",
        user=url.username,
        password=url.password,
        host=url.host or "localhost",
        port=url.port or 5432,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{url.database}"')
    conn.close()


@pytest.fixture
async def db_engine():
    # NullPool: connections die with each test's event loop, so nothing leaks across loops.
    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers (imported by test modules)
# ---------------------------------------------------------------------------

async def create_user(client: AsyncClient, username: str, metro: str = "345"):
    """Sign up a user; returns (user_id, auth_headers)."""
    resp = await client.post(
        "/auth/signup",
        json={
            "email": f"{username}@example.com",
            "username": username,
            "display_name": username.capitalize(),
            "password": "password123",
            "home_metro_id": metro,
        },
    )
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"], headers


async def befriend(client: AsyncClient, headers_a, id_a: str, headers_b, id_b: str):
    """a requests b; b accepts."""
    r = await client.post("/friends/requests", json={"user_id": id_b}, headers=headers_a)
    assert r.status_code == 201, r.text
    r = await client.post(f"/friends/requests/{id_a}/accept", headers=headers_b)
    assert r.status_code == 200, r.text


async def make_event(db_session, name: str = "Test Show", metro: str = "345",
                     genre: str = "Rock", days_ahead: int = 30) -> str:
    event = Event(
        tm_event_id=f"tm-{uuid.uuid4()}",
        name=name,
        metro_id=metro,
        genre=genre,
        starts_at=datetime.now(timezone.utc) + timedelta(days=days_ahead),
        venue_name="Test Venue",
    )
    db_session.add(event)
    await db_session.commit()
    return event.id


async def give_genre(db_session, user_id: str, genre: str = "Rock"):
    db_session.add(UserGenre(user_id=user_id, genre=genre))
    await db_session.commit()
