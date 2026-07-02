"""
Internal-only endpoints for ops/debugging. Not exposed to the mobile client.
Protected by a simple static token from the env for now.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.services.event_sync import sync_genres, sync_metro

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_admin_token: str = Header(...)):
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/sync/{metro_id}", dependencies=[Depends(_require_admin)])
async def trigger_sync(metro_id: str):
    count = await sync_metro(metro_id)
    return {"metro_id": metro_id, "events_upserted": count}


@router.post("/sync-genres", dependencies=[Depends(_require_admin)])
async def trigger_genre_sync():
    count = await sync_genres()
    return {"genres_upserted": count}
