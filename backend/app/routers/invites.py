import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Friendship, Invite, InviteRedemption, User
from app.services import social

router = APIRouter(prefix="/invites", tags=["invites"])

INVITE_TTL_DAYS = 7
INVITE_MAX_USES = 25
# lowercase + digits: easy to read aloud and type on a phone keyboard
_TOKEN_ALPHABET = string.ascii_lowercase + string.digits


def _new_token() -> str:
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(10))


def _invite_url(request: Request, token: str) -> str:
    base = settings.public_base_url or str(request.base_url)
    return f"{base.rstrip('/')}/invites/{token}"


class InviteResponse(BaseModel):
    token: str
    url: str
    max_uses: int
    expires_at: datetime


class RedeemResponse(BaseModel):
    friend: dict


def _is_dead(invite: Invite) -> bool:
    """Revoked or expired (cap is checked separately — it needs a count)."""
    now = datetime.now(timezone.utc)
    return invite.revoked_at is not None or invite.expires_at < now


@router.post("", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = Invite(
        token=_new_token(),
        inviter_id=current_user.id,
        max_uses=INVITE_MAX_USES,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()
    return InviteResponse(
        token=invite.token,
        url=_invite_url(request, invite.token),
        max_uses=invite.max_uses,
        expires_at=invite.expires_at,
    )


@router.get("/{token}", response_class=HTMLResponse)
async def landing_page(token: str, db: AsyncSession = Depends(get_db)):
    """Public page the invite link points at: context + the code + instructions.

    The QR your friends scan is just this URL rendered.
    """
    invite = await db.get(Invite, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    if _is_dead(invite):
        return HTMLResponse(
            "<html><body><h1>This invite link is no longer valid.</h1>"
            "<p>Ask your friend for a fresh one!</p></body></html>",
            status_code=status.HTTP_410_GONE,
        )

    inviter = await db.get(User, invite.inviter_id)
    inviter_name = inviter.display_name if inviter else "A friend"
    return HTMLResponse(
        f"""<html>
  <head><title>Concert With Friends — you're invited</title></head>
  <body style="font-family: sans-serif; max-width: 28rem; margin: 4rem auto; text-align: center;">
    <h1>🎸 {inviter_name} invited you to Concert With Friends</h1>
    <p>See which concerts are coming near you — and which friends want to go.</p>
    <ol style="text-align: left;">
      <li>Open the Concert With Friends app and sign up.</li>
      <li>On the Friends tab, tap <b>Enter invite code</b>.</li>
      <li>Enter this code:</li>
    </ol>
    <p style="font-size: 2rem; letter-spacing: 0.3rem; font-weight: bold;">{invite.token}</p>
  </body>
</html>"""
    )


@router.post("/{token}/redeem", response_model=RedeemResponse)
async def redeem(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = await db.get(Invite, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.inviter_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't redeem your own invite")
    if _is_dead(invite):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite is no longer valid")

    # The block wins over the invite — and the error stays generic.
    if await social.is_blocked_between(db, current_user.id, invite.inviter_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    already = await db.get(InviteRedemption, (token, current_user.id))
    if already is None:
        used = (
            await db.execute(
                select(func.count()).select_from(InviteRedemption).where(InviteRedemption.token == token)
            )
        ).scalar_one()
        if used >= invite.max_uses:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite is no longer valid")
        db.add(InviteRedemption(token=token, user_id=current_user.id))

    # Generating the link was the inviter's consent: friendship is accepted instantly.
    pair = await social.get_pair(db, current_user.id, invite.inviter_id)
    if pair is None:
        db.add(
            Friendship(
                requester_id=invite.inviter_id,
                addressee_id=current_user.id,
                status="accepted",
            )
        )
    elif pair.status == "pending":
        pair.status = "accepted"
    # accepted: already friends — idempotent

    await db.commit()

    inviter = await db.get(User, invite.inviter_id)
    return RedeemResponse(
        friend={
            "id": inviter.id,
            "username": inviter.username,
            "display_name": inviter.display_name,
        }
    )


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = await db.get(Invite, token)
    if invite is None or invite.inviter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        await db.commit()
