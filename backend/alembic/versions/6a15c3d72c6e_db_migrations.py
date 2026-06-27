"""db migrations

Revision ID: 6a15c3d72c6e
Revises:
Create Date: 2026-06-27 13:40:05.043050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6a15c3d72c6e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("home_metro_id", sa.Text(), nullable=True),
        sa.Column("location_precision", sa.Text(), nullable=False, server_default="metro"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("location_precision IN ('metro','city')", name="ck_users_location_precision"),
    )

    op.create_table(
        "artists",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tm_attraction_id", sa.Text(), nullable=True, unique=True),
        sa.Column("spotify_id", sa.Text(), nullable=True, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    op.create_table(
        "user_artists",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("artist_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weight", sa.SmallInteger(), nullable=False, server_default="1"),
    )

    op.create_table(
        "user_genres",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre", sa.Text(), primary_key=True),
    )

    op.create_table(
        "friendships",
        sa.Column("requester_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("addressee_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','accepted','blocked')", name="ck_friendships_status"),
        sa.CheckConstraint("requester_id <> addressee_id", name="ck_friendships_no_self"),
    )
    # One row per unordered pair (prevents A->B and B->A both existing)
    op.create_index(
        "friendship_pair_uniq",
        "friendships",
        [sa.text("least(requester_id, addressee_id)"), sa.text("greatest(requester_id, addressee_id)")],
        unique=True,
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tm_event_id", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("artists.id"), nullable=True),
        sa.Column("venue_name", sa.Text(), nullable=True),
        sa.Column("metro_id", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("genre", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "event_interest",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.CheckConstraint("level IN ('going','maybe')", name="ck_event_interest_level"),
    )

    op.create_table(
        "notifications_sent",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "device_tokens",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("platform IN ('ios','android')", name="ck_device_tokens_platform"),
    )


def downgrade() -> None:
    op.drop_table("device_tokens")
    op.drop_table("notifications_sent")
    op.drop_table("event_interest")
    op.drop_table("events")
    op.drop_index("friendship_pair_uniq", table_name="friendships")
    op.drop_table("friendships")
    op.drop_table("user_genres")
    op.drop_table("user_artists")
    op.drop_table("artists")
    op.drop_table("users")
