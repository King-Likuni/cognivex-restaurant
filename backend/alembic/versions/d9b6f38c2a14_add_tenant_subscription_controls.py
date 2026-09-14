"""Add tenant subscription controls

Revision ID: d9b6f38c2a14
Revises: c4e7f2a91d30
Create Date: 2026-09-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9b6f38c2a14"
down_revision: str | Sequence[str] | None = "c4e7f2a91d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track platform subscription state separately from tenant service state."""
    op.add_column(
        "restaurants",
        sa.Column("subscription_status", sa.String(), server_default="TRIAL", nullable=False),
    )
    op.add_column(
        "restaurants",
        sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column("subscription_renews_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("restaurants", sa.Column("suspension_reason", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove platform subscription state."""
    op.drop_column("restaurants", "suspension_reason")
    op.drop_column("restaurants", "subscription_renews_at")
    op.drop_column("restaurants", "subscription_started_at")
    op.drop_column("restaurants", "subscription_status")
