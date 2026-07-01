from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Event, EventInterest, Friendship, User, UserArtist, UserGenre
from app.services import social

router = APIRouter(prefix="/friends", tags=["friends"])


class FriendUserResponse(BaseModel):
    id: str
    username: str | None
    display_name: str

    class Config:
        from_attributes = True


class FriendRequestsResponse(BaseModel):
    incoming: list[FriendUserResponse]
    outgoing: list[FriendUserResponse]


class SendRequestBody(BaseModel):
    user_id: str


class ProfileArtist(BaseModel):
    name: str
    weight: int


class ProfileInterest(BaseModel):
    event_id: str
    event_name: str
    venue_name: str | None
    starts_at: datetime | None
    level: str


class FriendProfileResponse(BaseModel):
    id: str
    username: str | None
    display_name: str
    home_metro_id: str | None
    artists: list[ProfileArtist]
    genres: list[str]
    interests: list[ProfileInterest]


# A generic 404 for every case where the target must stay invisible (unknown user,
# blocked either direction). Never reveals which one it was.
_not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("", response_model=list[FriendUserResponse])
async def list_friends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ids = await social.friend_ids(db, current_user.id)
    if not ids:
        return []
    result = await db.execute(select(User).where(User.id.in_(ids)).order_by(User.display_name))
    return result.scalars().all()


@router.get("/requests", response_model=FriendRequestsResponse)
async def list_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Friendship).where(
            social.involves_clause(current_user.id), Friendship.status == "pending"
        )
    )
    rows = result.scalars().all()
    incoming_ids = [f.requester_id for f in rows if f.addressee_id == current_user.id]
    outgoing_ids = [f.addressee_id for f in rows if f.requester_id == current_user.id]

    async def _users(ids: list[str]) -> list[User]:
        if not ids:
            return []
        res = await db.execute(select(User).where(User.id.in_(ids)))
        return list(res.scalars().all())

    return FriendRequestsResponse(
        incoming=[FriendUserResponse.model_validate(u) for u in await _users(incoming_ids)],
        outgoing=[FriendUserResponse.model_validate(u) for u in await _users(outgoing_ids)],
    )


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def send_request(
    body: SendRequestBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot friend yourself")

    target = await db.get(User, body.user_id)
    if target is None:
        raise _not_found

    pair = await social.get_pair(db, current_user.id, body.user_id)
    if pair is not None:
        if pair.status == "blocked":
            raise _not_found  # never reveal a block
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A friendship or pending request already exists",
        )

    db.add(Friendship(requester_id=current_user.id, addressee_id=body.user_id, status="pending"))
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race with a simultaneous reverse request; same outcome as the pair check.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A friendship or pending request already exists",
        )
    return {"status": "pending"}


@router.post("/requests/{requester_id}/accept")
async def accept_request(
    requester_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == requester_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending",
        )
    )
    pair = result.scalar_one_or_none()
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending request from this user")
    pair.status = "accepted"
    await db.commit()
    return {"status": "accepted"}


@router.delete("/requests/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def decline_or_cancel_request(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Decline an incoming request from user_id, or cancel my outgoing one to them."""
    pair = await social.get_pair(db, current_user.id, user_id)
    if pair is None or pair.status != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending request with this user")
    await db.delete(pair)
    await db.commit()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfriend(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pair = await social.get_pair(db, current_user.id, user_id)
    if pair is None or pair.status != "accepted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not friends with this user")
    await db.delete(pair)
    await db.commit()


@router.post("/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def block(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself")
    target = await db.get(User, user_id)
    if target is None:
        raise _not_found

    pair = await social.get_pair(db, current_user.id, user_id)
    if pair is not None:
        if pair.status == "blocked":
            if pair.requester_id == current_user.id:
                return  # already blocked by me: idempotent
            raise _not_found  # they blocked me first; stay invisible
        await db.delete(pair)
        await db.flush()

    db.add(Friendship(requester_id=current_user.id, addressee_id=user_id, status="blocked"))
    await db.commit()


@router.delete("/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
async def unblock(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Friendship).where(
            Friendship.requester_id == current_user.id,  # only the blocker may unblock
            Friendship.addressee_id == user_id,
            Friendship.status == "blocked",
        )
    )
    pair = result.scalar_one_or_none()
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No block on this user")
    await db.delete(pair)
    await db.commit()


@router.get("/{user_id}/profile", response_model=FriendProfileResponse)
async def friend_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Friends-only: anyone else gets the same 404 as a nonexistent user.
    if not await social.are_friends(db, current_user.id, user_id):
        raise _not_found
    friend = await db.get(User, user_id)
    if friend is None:
        raise _not_found

    artist_rows = await db.execute(
        select(UserArtist)
        .options(selectinload(UserArtist.artist))
        .where(UserArtist.user_id == user_id)
    )
    artists = [
        ProfileArtist(name=ua.artist.name, weight=ua.weight)
        for ua in artist_rows.scalars().all()
    ]

    genre_rows = await db.execute(select(UserGenre.genre).where(UserGenre.user_id == user_id))
    genres = [r[0] for r in genre_rows.all()]

    interest_rows = await db.execute(
        select(EventInterest, Event)
        .join(Event, Event.id == EventInterest.event_id)
        .where(
            EventInterest.user_id == user_id,
            EventInterest.visibility == "shared",  # private interest never leaves the owner
            Event.starts_at >= datetime.now(timezone.utc),
        )
        .order_by(Event.starts_at)
    )
    interests = [
        ProfileInterest(
            event_id=event.id,
            event_name=event.name,
            venue_name=event.venue_name,
            starts_at=event.starts_at,
            level=interest.level,
        )
        for interest, event in interest_rows.all()
    ]

    return FriendProfileResponse(
        id=friend.id,
        username=friend.username,
        display_name=friend.display_name,
        home_metro_id=friend.home_metro_id,
        artists=artists,
        genres=genres,
        interests=interests,
    )
