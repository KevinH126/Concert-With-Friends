from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, User, UserArtist
from app.services.ticketmaster import resolve_artist

router = APIRouter(prefix="/artists", tags=["artists"])


class AddArtistRequest(BaseModel):
    name: str
    weight: int = 1


class ArtistResponse(BaseModel):
    id: str
    name: str
    tm_attraction_id: str | None
    weight: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[ArtistResponse])
async def list_my_artists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtist, Artist)
        .join(Artist, UserArtist.artist_id == Artist.id)
        .where(UserArtist.user_id == current_user.id)
    )
    rows = result.all()
    return [
        ArtistResponse(
            id=artist.id,
            name=artist.name,
            tm_attraction_id=artist.tm_attraction_id,
            weight=ua.weight,
        )
        for ua, artist in rows
    ]


@router.post("", response_model=ArtistResponse, status_code=status.HTTP_201_CREATED)
async def add_artist(
    body: AddArtistRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Resolve name → canonical artist row
    tm_id, canonical_name = await resolve_artist(body.name)

    # Find or create the artist row
    if tm_id:
        result = await db.execute(select(Artist).where(Artist.tm_attraction_id == tm_id))
    else:
        result = await db.execute(select(Artist).where(Artist.name == canonical_name))
    artist = result.scalar_one_or_none()

    if not artist:
        artist = Artist(name=canonical_name, tm_attraction_id=tm_id)
        db.add(artist)
        await db.flush()

    # Upsert user→artist link
    existing = await db.execute(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist.id,
        )
    )
    ua = existing.scalar_one_or_none()
    if ua:
        ua.weight = body.weight
    else:
        ua = UserArtist(user_id=current_user.id, artist_id=artist.id, weight=body.weight)
        db.add(ua)

    await db.commit()
    await db.refresh(artist)
    return ArtistResponse(id=artist.id, name=artist.name, tm_attraction_id=artist.tm_attraction_id, weight=body.weight)


@router.delete("/{artist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_artist(
    artist_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserArtist).where(
            UserArtist.user_id == current_user.id,
            UserArtist.artist_id == artist_id,
        )
    )
    ua = result.scalar_one_or_none()
    if not ua:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not in your list")
    await db.delete(ua)
    await db.commit()
