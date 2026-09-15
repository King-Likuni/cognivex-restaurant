"""Add platform incidents

Revision ID: a8f0c7e2d491
Revises: f2a4c9d7e813
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8f0c7e2d491"
down_revision: str | Sequence[str] | None = "f2a4c9d7e813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable platform incident records."""
    op.create_table(
        "platform_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_incidents_fingerprint",
        "platform_incidents",
        ["fingerprint"],
    )
    op.create_index(
        "ix_platform_incidents_restaurant_id",
        "platform_incidents",
        ["restaurant_id"],
    )
    op.create_index(
        "ix_platform_incidents_source_category",
        "platform_incidents",
        ["source", "category"],
    )
    op.create_index(
        "ix_platform_incidents_status_created_at",
        "platform_incidents",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Drop platform incidents."""
    op.drop_index("ix_platform_incidents_status_created_at", table_name="platform_incidents")
    op.drop_index("ix_platform_incidents_source_category", table_name="platform_incidents")
    op.drop_index("ix_platform_incidents_restaurant_id", table_name="platform_incidents")
    op.drop_index("ix_platform_incidents_fingerprint", table_name="platform_incidents")
    op.drop_table("platform_incidents")
