"""Add user created at

Revision ID: 9f0d3b2a7c55
Revises: 7c2a9f1e4b66
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f0d3b2a7c55"
down_revision: str | Sequence[str] | None = "7c2a9f1e4b66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track when a staff account was created."""
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove staff account creation timestamp."""
    op.drop_column("users", "created_at")
