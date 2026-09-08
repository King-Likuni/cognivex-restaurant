"""Phase 1 foundation upgrade

Revision ID: 8b3f6c2d1e90
Revises: 3e6a740f864b
Create Date: 2026-09-03 11:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "8b3f6c2d1e90"
down_revision: str | Sequence[str] | None = "3e6a740f864b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade existing local databases to the current foundation schema."""
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS code VARCHAR")
    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                UPPER(LEFT(REGEXP_REPLACE(name, '[^A-Za-z0-9]', '', 'g'), 4)) AS base_code,
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(LEFT(REGEXP_REPLACE(name, '[^A-Za-z0-9]', '', 'g'), 4))
                    ORDER BY created_at, id
                ) AS row_num
            FROM restaurants
            WHERE code IS NULL
        )
        UPDATE restaurants
        SET code = CASE
            WHEN numbered.row_num = 1 THEN COALESCE(NULLIF(numbered.base_code, ''), 'REST')
            ELSE LEFT(COALESCE(NULLIF(numbered.base_code, ''), 'REST'), 10) || numbered.row_num::TEXT
        END
        FROM numbered
        WHERE restaurants.id = numbered.id
        """
    )
    op.execute("ALTER TABLE restaurants ALTER COLUMN code SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_restaurants_code ON restaurants (code)")

    op.execute("ALTER TABLE branches ADD COLUMN IF NOT EXISTS code VARCHAR")
    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                restaurant_id,
                UPPER(LEFT(REGEXP_REPLACE(name, '[^A-Za-z0-9]', '', 'g'), 3)) AS base_code,
                ROW_NUMBER() OVER (
                    PARTITION BY restaurant_id, UPPER(LEFT(REGEXP_REPLACE(name, '[^A-Za-z0-9]', '', 'g'), 3))
                    ORDER BY id
                ) AS row_num
            FROM branches
            WHERE code IS NULL
        )
        UPDATE branches
        SET code = CASE
            WHEN numbered.row_num = 1 THEN COALESCE(NULLIF(numbered.base_code, ''), 'BR')
            ELSE LEFT(COALESCE(NULLIF(numbered.base_code, ''), 'BR'), 10) || numbered.row_num::TEXT
        END
        FROM numbered
        WHERE branches.id = numbered.id
        """
    )
    op.execute("ALTER TABLE branches ALTER COLUMN code SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_branches_restaurant_code'
            ) THEN
                ALTER TABLE branches
                ADD CONSTRAINT uq_branches_restaurant_code UNIQUE (restaurant_id, code);
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_reference VARCHAR")
    op.execute(
        """
        UPDATE orders
        SET payment_reference = restaurants.code || '-' || branches.code || '-' ||
            TO_CHAR(orders.business_date, 'YYMMDD') || '-' ||
            LPAD(orders.daily_sequence::TEXT, 3, '0')
        FROM restaurants, branches
        WHERE orders.restaurant_id = restaurants.id
            AND orders.branch_id = branches.id
            AND orders.payment_reference IS NULL
        """
    )
    op.execute("ALTER TABLE orders ALTER COLUMN payment_reference SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_payment_reference ON orders (payment_reference)"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_orders_daily_sequence_per_branch'
            ) THEN
                ALTER TABLE orders
                ADD CONSTRAINT uq_orders_daily_sequence_per_branch
                UNIQUE (restaurant_id, branch_id, business_date, daily_sequence);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_orders_display_number_per_branch'
            ) THEN
                ALTER TABLE orders
                ADD CONSTRAINT uq_orders_display_number_per_branch
                UNIQUE (restaurant_id, branch_id, business_date, display_number);
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ingredients (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            name VARCHAR NOT NULL,
            unit VARCHAR NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_ingredients_restaurant_name UNIQUE (restaurant_id, name)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ingredients_restaurant_id ON ingredients (restaurant_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_locations (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            branch_id UUID NOT NULL REFERENCES branches(id),
            name VARCHAR NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_stock_locations_branch_name UNIQUE (branch_id, name)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_locations_restaurant_id ON stock_locations (restaurant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_locations_branch_id ON stock_locations (branch_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_item_recipe_items (
            id UUID PRIMARY KEY,
            menu_item_id UUID NOT NULL REFERENCES menu_items(id),
            ingredient_id UUID NOT NULL REFERENCES ingredients(id),
            quantity NUMERIC(12, 3) NOT NULL,
            CONSTRAINT uq_recipe_menu_item_ingredient UNIQUE (menu_item_id, ingredient_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_menu_item_recipe_items_menu_item_id ON menu_item_recipe_items (menu_item_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_menu_item_recipe_items_ingredient_id ON menu_item_recipe_items (ingredient_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_movements (
            id UUID PRIMARY KEY,
            restaurant_id UUID NOT NULL REFERENCES restaurants(id),
            branch_id UUID NOT NULL REFERENCES branches(id),
            stock_location_id UUID NOT NULL REFERENCES stock_locations(id),
            ingredient_id UUID NOT NULL REFERENCES ingredients(id),
            movement_type VARCHAR NOT NULL,
            quantity NUMERIC(12, 3) NOT NULL,
            reference_type VARCHAR,
            reference_id UUID,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_restaurant_id ON stock_movements (restaurant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_branch_id ON stock_movements (branch_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_ingredient_id ON stock_movements (ingredient_id)"
    )

    op.execute("ALTER TABLE payment_events ADD COLUMN IF NOT EXISTS provider_event_id VARCHAR")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_payment_events_provider_event_id'
            ) THEN
                ALTER TABLE payment_events
                ADD CONSTRAINT uq_payment_events_provider_event_id
                UNIQUE (payment_id, provider_event_id);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_payments_provider_transaction_id'
            ) THEN
                ALTER TABLE payments
                ADD CONSTRAINT uq_payments_provider_transaction_id
                UNIQUE (provider, provider_transaction_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Downgrade Phase 1 foundation changes."""
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS uq_payments_provider_transaction_id")
    op.execute(
        "ALTER TABLE payment_events DROP CONSTRAINT IF EXISTS uq_payment_events_provider_event_id"
    )
    op.execute("ALTER TABLE payment_events DROP COLUMN IF EXISTS provider_event_id")

    op.execute("DROP INDEX IF EXISTS ix_stock_movements_ingredient_id")
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_branch_id")
    op.execute("DROP INDEX IF EXISTS ix_stock_movements_restaurant_id")
    op.execute("DROP TABLE IF EXISTS stock_movements")
    op.execute("DROP INDEX IF EXISTS ix_menu_item_recipe_items_ingredient_id")
    op.execute("DROP INDEX IF EXISTS ix_menu_item_recipe_items_menu_item_id")
    op.execute("DROP TABLE IF EXISTS menu_item_recipe_items")
    op.execute("DROP INDEX IF EXISTS ix_stock_locations_branch_id")
    op.execute("DROP INDEX IF EXISTS ix_stock_locations_restaurant_id")
    op.execute("DROP TABLE IF EXISTS stock_locations")
    op.execute("DROP INDEX IF EXISTS ix_ingredients_restaurant_id")
    op.execute("DROP TABLE IF EXISTS ingredients")

    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS uq_orders_display_number_per_branch")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS uq_orders_daily_sequence_per_branch")
    op.execute("DROP INDEX IF EXISTS ix_orders_payment_reference")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS payment_reference")

    op.execute("ALTER TABLE branches DROP CONSTRAINT IF EXISTS uq_branches_restaurant_code")
    op.execute("ALTER TABLE branches DROP COLUMN IF EXISTS code")
    op.execute("DROP INDEX IF EXISTS ix_restaurants_code")
    op.execute("ALTER TABLE restaurants DROP COLUMN IF EXISTS code")
