"""P3.5: nullable image_url on events (TM hero image for the feed card)

Revision ID: d1e4a7c9b2f5
Revises: c7d20a94f1b3
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e4a7c9b2f5"
down_revision: Union[str, None] = "c7d20a94f1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "image_url")
