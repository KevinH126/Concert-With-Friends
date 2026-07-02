"""P3 genre subsystem: tm_genres taxonomy, subgenre/url on events,
is_subgenre on user_genres, tm_upcoming_events popularity proxy on artists

Revision ID: c7d20a94f1b3
Revises: b3f9d41e8a02
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d20a94f1b3"
down_revision: Union[str, None] = "b3f9d41e8a02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tm_genres",
        sa.Column("tm_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_tm_id", sa.Text(), sa.ForeignKey("tm_genres.tm_id"), nullable=True),
    )

    op.add_column(
        "user_genres",
        sa.Column("is_subgenre", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.add_column("events", sa.Column("subgenre", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("url", sa.Text(), nullable=True))

    op.add_column("artists", sa.Column("tm_upcoming_events", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("artists", "tm_upcoming_events")
    op.drop_column("events", "url")
    op.drop_column("events", "subgenre")
    op.drop_column("user_genres", "is_subgenre")
    op.drop_table("tm_genres")
