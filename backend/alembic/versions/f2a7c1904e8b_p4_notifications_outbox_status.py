"""P4: transactional-outbox status on notifications_sent

Adds `status` (pending|sent) and makes `sent_at` nullable so a row can be claimed
'pending' (committed before the push) and flipped to 'sent' after delivery. Prod's
notifications_sent is empty (the pipeline has never run), so this is a safe additive
change; the server_default keeps it safe even if it weren't.

Revision ID: f2a7c1904e8b
Revises: d1e4a7c9b2f5
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a7c1904e8b"
down_revision: Union[str, None] = "d1e4a7c9b2f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications_sent",
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
    )
    op.create_check_constraint(
        "ck_notifications_sent_status",
        "notifications_sent",
        "status IN ('pending','sent')",
    )
    # sent_at is NULL until the send succeeds; drop the old NOT NULL + now() default.
    op.alter_column(
        "notifications_sent",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    # Backfill so the NOT NULL restore can't fail on pending (NULL sent_at) rows.
    op.execute("UPDATE notifications_sent SET sent_at = now() WHERE sent_at IS NULL")
    op.alter_column(
        "notifications_sent",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.drop_constraint("ck_notifications_sent_status", "notifications_sent", type_="check")
    op.drop_column("notifications_sent", "status")
