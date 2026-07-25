"""
Celery app + beat schedule for the P4 notification pipeline (centerpiece 1).

Prod runs worker + beat in ONE process at concurrency 1 (sequential metros keep the
Ticketmaster 5-req/sec ceiling safe without a distributed limiter):

    celery -A app.worker worker -B --concurrency=1 --loglevel=info

Each task builds a fresh engine bound to its own event loop (the module-level engine in
app.database is tied to whatever loop first used it; reusing it across the per-task loops
asyncio.run() creates raises "attached to a different loop"). NullPool = no connection
outlives the task.
"""
import asyncio

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import User
from app.services.event_sync import sync_metro
from app.services.notifications import (
    LogNotifier, flush_all_pending, notify_friend_mark, run_metro_pipeline,
)

celery_app = Celery("concert_friends", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.beat_schedule = {
    # One nightly orchestrator (2 AM UTC) — it derives the active metros itself.
    "nightly-notification-pipeline": {
        "task": "app.worker.nightly_pipeline_task",
        "schedule": crontab(hour=2, minute=0),
    },
}
celery_app.conf.timezone = "UTC"


def _engine():
    return create_async_engine(settings.async_database_url, poolclass=NullPool)


async def _run_nightly() -> int:
    """Active metros come from the users themselves — a friend in a new metro is covered
    the night they set their home metro; empty set = clean no-op. Each metro syncs then
    digests its new events; a final sweep recovers any stuck-pending sends."""
    engine = _engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    notifier = LogNotifier()

    async def _sync(metro_id: str) -> None:
        await sync_metro(metro_id, session_factory=factory)

    try:
        async with factory() as db:
            metros = (
                await db.execute(
                    select(User.home_metro_id)
                    .where(User.home_metro_id.isnot(None))
                    .distinct()
                )
            ).scalars().all()

        for metro_id in metros:
            async with factory() as db:
                await run_metro_pipeline(db, metro_id, notifier, sync=_sync)

        async with factory() as db:
            await flush_all_pending(db, notifier)
    finally:
        await engine.dispose()

    return len(metros)


async def _run_friend_mark(marker_id: str, event_id: str) -> None:
    engine = _engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            await notify_friend_mark(db, marker_id, event_id, LogNotifier())
    finally:
        await engine.dispose()


@celery_app.task(name="app.worker.nightly_pipeline_task")
def nightly_pipeline_task() -> int:
    return asyncio.run(_run_nightly())


@celery_app.task(name="app.worker.friend_mark_ping_task")
def friend_mark_ping_task(marker_id: str, event_id: str) -> None:
    asyncio.run(_run_friend_mark(marker_id, event_id))


@celery_app.task(name="app.worker.sync_metro_task")
def sync_metro_task(metro_id: str) -> int:
    """Kept for manual/admin one-off syncs (the P1 mechanism)."""
    async def _run() -> int:
        engine = _engine()
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            return await sync_metro(metro_id, session_factory=factory)
        finally:
            await engine.dispose()

    return asyncio.run(_run())
