"""Add inventory role

Revision ID: b1e4d6a8c9f2
Revises: 9f0d3b2a7c55
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "b1e4d6a8c9f2"
down_revision: str | Sequence[str] | None = "9f0d3b2a7c55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the branch-scoped inventory worker role."""
    op.execute(
        sa.text(
            """
            INSERT INTO roles (id, name)
            SELECT :role_id, :role_name
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE name = :role_name
            )
            """
        ).bindparams(role_id=str(uuid4()), role_name="INVENTORY")
    )


def downgrade() -> None:
    """Remove the inventory role only when no users are assigned to it."""
    op.execute(
        sa.text(
            """
            DELETE FROM roles
            WHERE name = 'INVENTORY'
              AND NOT EXISTS (
                  SELECT 1 FROM users WHERE users.role_id = roles.id
              )
            """
        )
    )
