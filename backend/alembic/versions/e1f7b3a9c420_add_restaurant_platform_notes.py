"""Add restaurant platform notes

Revision ID: e1f7b3a9c420
Revises: a8f0c7e2d491
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f7b3a9c420"
down_revision: str | Sequence[str] | None = "a8f0c7e2d491"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store private platform operator notes for restaurant tenants."""
    op.add_column("restaurants", sa.Column("platform_notes", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove private platform operator notes."""
    op.drop_column("restaurants", "platform_notes")
