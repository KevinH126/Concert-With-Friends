"""Shared friendship-pair helpers. One row per unordered pair; requester_id doubles
as 'who blocked' when status='blocked'."""
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Friendship


def pair_clause(user_a: str, user_b: str):
    return or_(
        and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
        and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
    )


def involves_clause(user_id: str):
    return or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id)


async def get_pair(db: AsyncSession, user_a: str, user_b: str) -> Friendship | None:
    result = await db.execute(select(Friendship).where(pair_clause(user_a, user_b)))
    return result.scalar_one_or_none()


async def are_friends(db: AsyncSession, user_a: str, user_b: str) -> bool:
    pair = await get_pair(db, user_a, user_b)
    return pair is not None and pair.status == "accepted"


async def is_blocked_between(db: AsyncSession, user_a: str, user_b: str) -> bool:
    pair = await get_pair(db, user_a, user_b)
    return pair is not None and pair.status == "blocked"


async def friend_ids(db: AsyncSession, user_id: str) -> list[str]:
    result = await db.execute(
        select(Friendship).where(involves_clause(user_id), Friendship.status == "accepted")
    )
    return [
        f.addressee_id if f.requester_id == user_id else f.requester_id
        for f in result.scalars().all()
    ]


async def relationships_of(db: AsyncSession, user_id: str) -> dict[str, Friendship]:
    """Map of other-user-id -> pair row, for every row involving user_id."""
    result = await db.execute(select(Friendship).where(involves_clause(user_id)))
    rel: dict[str, Friendship] = {}
    for f in result.scalars().all():
        other = f.addressee_id if f.requester_id == user_id else f.requester_id
        rel[other] = f
    return rel


def status_label(pair: Friendship | None, viewer_id: str) -> str:
    """Friendship status from the viewer's perspective: none|pending_out|pending_in|friends|blocked."""
    if pair is None:
        return "none"
    if pair.status == "accepted":
        return "friends"
    if pair.status == "pending":
        return "pending_out" if pair.requester_id == viewer_id else "pending_in"
    return "blocked"
