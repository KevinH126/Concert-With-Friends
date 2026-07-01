import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.routers.auth import USERNAME_PATTERN
from app.services import social

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    username: str | None = Field(None, pattern=USERNAME_PATTERN)
    home_metro_id: str | None = None
    location_precision: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    username: str | None
    display_name: str
    home_metro_id: str | None
    location_precision: str

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    id: str
    username: str
    display_name: str
    friendship_status: str  # none | pending_out | pending_in | friends


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.username is not None and body.username != current_user.username:
        taken = await db.execute(select(User).where(User.username == body.username))
        if taken.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
        current_user.username = body.username
    if body.home_metro_id is not None:
        current_user.home_metro_id = body.home_metro_id
    if body.location_precision is not None and body.location_precision in ("metro", "city"):
        current_user.location_precision = body.location_precision

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    await db.refresh(current_user)
    return current_user


@router.get("/search", response_model=list[SearchResult])
async def search_users(
    q: str = Query(min_length=3, max_length=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Prefix search on username. Excludes yourself and anyone in a blocked
    relationship with you (either direction)."""
    prefix = q.lower()
    if not re.fullmatch(r"[a-z0-9_]+", prefix):
        return []

    # '_' is legal in usernames but a LIKE wildcard — escape it.
    escaped = prefix.replace("\\", "\\\\").replace("_", "\\_")
    result = await db.execute(
        select(User)
        .where(User.username.like(f"{escaped}%", escape="\\"), User.id != current_user.id)
        .order_by(User.username)
        .limit(25)
    )
    candidates = result.scalars().all()

    rel = await social.relationships_of(db, current_user.id)
    results: list[SearchResult] = []
    for user in candidates:
        pair = rel.get(user.id)
        label = social.status_label(pair, current_user.id)
        if label == "blocked":
            continue  # invisible both directions
        results.append(
            SearchResult(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                friendship_status=label,
            )
        )
        if len(results) >= 10:
            break
    return results
