"""P2 social graph: username, invites, invite_redemptions, interest visibility

Revision ID: b3f9d41e8a02
Revises: 6a15c3d72c6e
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3f9d41e8a02"
down_revision: Union[str, None] = "6a15c3d72c6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Required at signup from P2 on (API-enforced); nullable for legacy accounts.
    op.add_column("users", sa.Column("username", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    op.add_column(
        "event_interest",
        sa.Column("visibility", sa.Text(), nullable=False, server_default="shared"),
    )
    op.create_check_constraint(
        "ck_event_interest_visibility",
        "event_interest",
        "visibility IN ('shared','private')",
    )

    op.create_table(
        "invites",
        sa.Column("token", sa.Text(), primary_key=True),
        sa.Column(
            "inviter_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("max_uses", sa.SmallInteger(), nullable=False, server_default="25"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "invite_redemptions",
        sa.Column("token", sa.Text(), sa.ForeignKey("invites.token", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("invite_redemptions")
    op.drop_table("invites")
    op.drop_constraint("ck_event_interest_visibility", "event_interest", type_="check")
    op.drop_column("event_interest", "visibility")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "username")
