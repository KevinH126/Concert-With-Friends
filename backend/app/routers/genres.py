from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import TmGenre, User, UserGenre

router = APIRouter(prefix="/genres", tags=["genres"])


class AddGenreRequest(BaseModel):
    genre: str


class TaxonomyGenre(BaseModel):
    name: str
    subgenres: list[str]


@router.get("/taxonomy", response_model=list[TaxonomyGenre])
async def genre_taxonomy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The picker's data: broad genres with their sub-genres, from the TM taxonomy
    cache. Empty until an admin runs POST /admin/sync-genres."""
    result = await db.execute(select(TmGenre))
    rows = result.scalars().all()
    by_id = {row.tm_id: row for row in rows}
    grouped: dict[str, list[str]] = {row.name: [] for row in rows if row.parent_tm_id is None}
    for row in rows:
        if row.parent_tm_id is not None:
            parent = by_id.get(row.parent_tm_id)
            # TM's same-named subgenres ("Rock" under "Rock") are noise in a picker.
            if parent is not None and row.name != parent.name:
                grouped.setdefault(parent.name, []).append(row.name)
    return [
        TaxonomyGenre(name=name, subgenres=sorted(subs))
        for name, subs in sorted(grouped.items())
    ]


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
    # The P1 free-text box is dead: genres must come from the TM taxonomy (canonical
    # casing included — this is what fixes the silent case-mismatch matching bug).
    # TM has a same-named subgenre under nearly every broad genre ("Rock" → "Rock");
    # an ambiguous name resolves to the broad genre (wider hierarchical net).
    tm_rows = await db.execute(select(TmGenre).where(TmGenre.name == body.genre))
    candidates = tm_rows.scalars().all()
    tm_genre = next((g for g in candidates if g.parent_tm_id is None), None) or (
        candidates[0] if candidates else None
    )
    if tm_genre is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Genre must be picked from the taxonomy (GET /genres/taxonomy)",
        )

    existing = await db.execute(
        select(UserGenre).where(
            UserGenre.user_id == current_user.id,
            UserGenre.genre == body.genre,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(UserGenre(
            user_id=current_user.id,
            genre=tm_genre.name,
            is_subgenre=tm_genre.parent_tm_id is not None,
        ))
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
