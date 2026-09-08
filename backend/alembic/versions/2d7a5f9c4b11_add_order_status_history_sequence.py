"""Add deterministic order status history sequence

Revision ID: 2d7a5f9c4b11
Revises: 8b3f6c2d1e90
Create Date: 2026-09-04 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2d7a5f9c4b11"
down_revision: str | Sequence[str] | None = "8b3f6c2d1e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store a deterministic per-order order-status history position."""
    op.execute("ALTER TABLE order_status_history ADD COLUMN IF NOT EXISTS sequence INTEGER")
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY changed_at NULLS FIRST, id
                ) AS row_sequence
            FROM order_status_history
        )
        UPDATE order_status_history
        SET sequence = ranked.row_sequence
        FROM ranked
        WHERE order_status_history.id = ranked.id
            AND order_status_history.sequence IS NULL
        """
    )
    op.execute("ALTER TABLE order_status_history ALTER COLUMN sequence SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'order_status_history'::regclass
                    AND conname = 'uq_order_status_history_order_sequence'
            ) THEN
                ALTER TABLE order_status_history
                ADD CONSTRAINT uq_order_status_history_order_sequence
                UNIQUE (order_id, sequence);
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_order_status_history_order_sequence "
        "ON order_status_history (order_id, sequence)"
    )


def downgrade() -> None:
    """Remove deterministic status-history sequencing."""
    op.execute("DROP INDEX IF EXISTS ix_order_status_history_order_sequence")
    op.execute(
        "ALTER TABLE order_status_history "
        "DROP CONSTRAINT IF EXISTS uq_order_status_history_order_sequence"
    )
    op.execute("ALTER TABLE order_status_history DROP COLUMN IF EXISTS sequence")
