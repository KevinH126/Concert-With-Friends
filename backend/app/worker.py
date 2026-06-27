"""
Celery app + beat schedule for periodic event syncing.

Run worker:  celery -A app.worker worker --loglevel=info
Run beat:    celery -A app.worker beat --loglevel=info
"""
import asyncio

from celery import Celery
from celery.schedules import crontab

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


@celery_app.task(name="app.worker.sync_metro_task")
def sync_metro_task(metro_id: str) -> int:
    from app.services.event_sync import sync_metro
    return asyncio.run(sync_metro(metro_id))
