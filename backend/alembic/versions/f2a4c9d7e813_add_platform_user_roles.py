"""Add platform user roles

Revision ID: f2a4c9d7e813
Revises: d9b6f38c2a14
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a4c9d7e813"
down_revision: str | Sequence[str] | None = "d9b6f38c2a14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support platform-only users and platform-level audit events."""
    op.alter_column("audit_logs", "restaurant_id", nullable=True)
    op.execute(
        """
        insert into roles (id, name)
        values
            ('4c8f65a5-81dd-4b7d-922d-6d091f3c61b7', 'SUPPORT'),
            ('3fd33b5c-6194-4639-8059-3cabee81c19e', 'FINANCE')
        on conflict (name) do nothing
        """
    )


def downgrade() -> None:
    """Remove platform-only roles."""
    op.execute("delete from audit_logs where restaurant_id is null")
    op.execute("delete from roles where name in ('SUPPORT', 'FINANCE')")
    op.alter_column("audit_logs", "restaurant_id", nullable=False)
