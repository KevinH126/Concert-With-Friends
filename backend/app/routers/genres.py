from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User, UserGenre

router = APIRouter(prefix="/genres", tags=["genres"])


class AddGenreRequest(BaseModel):
    genre: str


@router.get("", response_model=list[str])
async def list_my_genres(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserGenre.genre).where(UserGenre.user_id == current_user.id))
    return [row[0] for row in result.all()]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=list[str])
async def add_genre(
    body: AddGenreRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(UserGenre).where(
            UserGenre.user_id == current_user.id,
            UserGenre.genre == body.genre,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserGenre(user_id=current_user.id, genre=body.genre))
        await db.commit()

    result = await db.execute(select(UserGenre.genre).where(UserGenre.user_id == current_user.id))
    return [row[0] for row in result.all()]


@router.delete("/{genre}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_genre(
    genre: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserGenre).where(
            UserGenre.user_id == current_user.id,
            UserGenre.genre == genre,
        )
    )
    ug = result.scalar_one_or_none()
    if not ug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Genre not in your list")
    await db.delete(ug)
    await db.commit()
