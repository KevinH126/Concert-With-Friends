"""Enqueue seam between request handlers and the Celery worker.

Kept tiny and defensive: enqueuing is best-effort, so a broker outage (or a test
environment with no Redis) can never fail the user request that triggered it.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def enqueue_friend_mark_ping(marker_id: str, event_id: str) -> None:
    """Fire the friend-mark ping off the request path. No-op when enqueuing is
    disabled (tests); swallows broker errors so marking interest never fails on it."""
    if not settings.notifications_enqueue:
        return
    try:
        from app.worker import friend_mark_ping_task

        friend_mark_ping_task.delay(marker_id, event_id)
    except Exception:  # noqa: BLE001 — the mark already succeeded; the ping is best-effort
        logger.warning("Could not enqueue friend-mark ping for %s / %s", marker_id, event_id)
