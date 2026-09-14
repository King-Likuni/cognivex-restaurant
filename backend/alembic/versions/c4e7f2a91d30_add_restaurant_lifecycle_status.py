"""Add restaurant lifecycle status

Revision ID: c4e7f2a91d30
Revises: b1e4d6a8c9f2
Create Date: 2026-09-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7f2a91d30"
down_revision: str | Sequence[str] | None = "b1e4d6a8c9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track tenant lifecycle separately from legacy active flag."""
    op.add_column(
        "restaurants",
        sa.Column("status", sa.String(), server_default="ACTIVE", nullable=False),
    )
    op.execute(
        """
        update restaurants
        set status = case when is_active then 'ACTIVE' else 'SUSPENDED' end
        """
    )


def downgrade() -> None:
    """Remove restaurant lifecycle status."""
    op.drop_column("restaurants", "status")
