"""Add stock thresholds

Revision ID: 7c2a9f1e4b66
Revises: 4a9d8c1b2f33
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c2a9f1e4b66"
down_revision: str | Sequence[str] | None = "4a9d8c1b2f33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store branch-level low-stock alert thresholds."""
    op.create_table(
        "stock_thresholds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("restaurant_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("warning_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("critical_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "restaurant_id",
            "branch_id",
            "ingredient_id",
            name="uq_stock_thresholds_branch_ingredient",
        ),
    )
    op.create_index(
        op.f("ix_stock_thresholds_branch_id"),
        "stock_thresholds",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_thresholds_restaurant_id"),
        "stock_thresholds",
        ["restaurant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove branch-level low-stock alert thresholds."""
    op.drop_index(op.f("ix_stock_thresholds_restaurant_id"), table_name="stock_thresholds")
    op.drop_index(op.f("ix_stock_thresholds_branch_id"), table_name="stock_thresholds")
    op.drop_table("stock_thresholds")
