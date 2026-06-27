from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    home_metro_id: str | None = None
    location_precision: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    home_metro_id: str | None
    location_precision: str

    class Config:
        from_attributes = True


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.home_metro_id is not None:
        current_user.home_metro_id = body.home_metro_id
    if body.location_precision is not None and body.location_precision in ("metro", "city"):
        current_user.location_precision = body.location_precision

    await db.commit()
    await db.refresh(current_user)
    return current_user
