"""
Celery app + beat schedule for periodic event syncing.

Run worker:  celery -A app.worker worker --loglevel=info
Run beat:    celery -A app.worker beat --loglevel=info
"""
import asyncio

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

celery_app = Celery("concert_friends", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.beat_schedule = {
    # Sync events nightly at 2 AM. Add more metro IDs as needed.
    "sync-events-nightly": {
        "task": "app.worker.sync_metro_task",
        "schedule": crontab(hour=2, minute=0),
        "args": ["DMA_123"],  # Replace with your Ticketmaster DMA id
    },
}
celery_app.conf.timezone = "UTC"


async def _run_sync(metro_id: str) -> int:
    # Build a fresh engine bound to *this* event loop. The module-level engine in
    # app.database is tied to whatever loop first used it; reusing it across the
    # per-task loops that asyncio.run() creates raises "attached to a different
    # loop" errors. NullPool means no connections outlive the task.
    from app.services.event_sync import sync_metro

    engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        return await sync_metro(metro_id, session_factory=factory)
    finally:
        await engine.dispose()


@celery_app.task(name="app.worker.sync_metro_task")
def sync_metro_task(metro_id: str) -> int:
    return asyncio.run(_run_sync(metro_id))
