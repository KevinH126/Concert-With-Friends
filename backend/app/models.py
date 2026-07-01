import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey,
    Index, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(Text, unique=True, nullable=False)
    # Required at signup (enforced in the API) from P2 on; nullable in the DB only
    # for legacy pre-P2 accounts, which set theirs via PATCH /users/me.
    username = Column(Text, unique=True, nullable=True)
    display_name = Column(Text, nullable=False)
    hashed_password = Column(Text, nullable=False)
    home_metro_id = Column(Text, nullable=True)
    location_precision = Column(
        Text,
        nullable=False,
        default="metro",
        server_default="metro",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("location_precision IN ('metro','city')", name="ck_users_location_precision"),
    )

    artists = relationship("UserArtist", back_populates="user", cascade="all, delete-orphan")
    genres = relationship("UserGenre", back_populates="user", cascade="all, delete-orphan")
    device_tokens = relationship("DeviceToken", back_populates="user", cascade="all, delete-orphan")
    event_interests = relationship("EventInterest", back_populates="user", cascade="all, delete-orphan")


class Artist(Base):
    __tablename__ = "artists"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tm_attraction_id = Column(Text, unique=True, nullable=True)
    spotify_id = Column(Text, unique=True, nullable=True)
    name = Column(Text, nullable=False)

    user_artists = relationship("UserArtist", back_populates="artist")
    events = relationship("Event", back_populates="artist")


class UserArtist(Base):
    __tablename__ = "user_artists"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    artist_id = Column(UUID(as_uuid=False), ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True)
    weight = Column(SmallInteger, nullable=False, default=1)

    user = relationship("User", back_populates="artists")
    artist = relationship("Artist", back_populates="user_artists")


class UserGenre(Base):
    __tablename__ = "user_genres"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    genre = Column(Text, primary_key=True)

    user = relationship("User", back_populates="genres")


class Friendship(Base):
    __tablename__ = "friendships"

    requester_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    addressee_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','blocked')", name="ck_friendships_status"),
        CheckConstraint("requester_id <> addressee_id", name="ck_friendships_no_self"),
        # One row per unordered pair
        Index(
            "friendship_pair_uniq",
            func.least(requester_id, addressee_id),
            func.greatest(requester_id, addressee_id),
            unique=True,
        ),
    )


class Invite(Base):
    """Multi-use invite link: one token serves the whole group chat.

    Redeeming creates an instant 'accepted' friendship with the inviter — generating
    the link is the inviter's consent, so there is no approval step.
    """

    __tablename__ = "invites"

    token = Column(Text, primary_key=True)
    inviter_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    max_uses = Column(SmallInteger, nullable=False, default=25, server_default="25")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)  # soft revoke keeps the audit trail
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    redemptions = relationship("InviteRedemption", back_populates="invite", cascade="all, delete-orphan")


class InviteRedemption(Base):
    __tablename__ = "invite_redemptions"

    token = Column(Text, ForeignKey("invites.token", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    invite = relationship("Invite", back_populates="redemptions")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tm_event_id = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    artist_id = Column(UUID(as_uuid=False), ForeignKey("artists.id"), nullable=True)
    venue_name = Column(Text, nullable=True)
    metro_id = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    genre = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    artist = relationship("Artist", back_populates="events")
    interests = relationship("EventInterest", back_populates="event", cascade="all, delete-orphan")


class EventInterest(Base):
    __tablename__ = "event_interest"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_id = Column(UUID(as_uuid=False), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    level = Column(Text, nullable=False)
    # Private interest still feeds YOUR notifications/feed, but is hidden from friends
    # and excluded from the match results friends see about you.
    visibility = Column(Text, nullable=False, default="shared", server_default="shared")

    __table_args__ = (
        CheckConstraint("level IN ('going','maybe')", name="ck_event_interest_level"),
        CheckConstraint("visibility IN ('shared','private')", name="ck_event_interest_visibility"),
    )

    user = relationship("User", back_populates="event_interests")
    event = relationship("Event", back_populates="interests")


class NotificationSent(Base):
    __tablename__ = "notifications_sent"

    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_id = Column(UUID(as_uuid=False), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    token = Column(Text, primary_key=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("platform IN ('ios','android')", name="ck_device_tokens_platform"),
    )

    user = relationship("User", back_populates="device_tokens")
