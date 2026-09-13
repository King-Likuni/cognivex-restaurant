"""Phase 2 inventory models.

These tables are intentionally isolated from MVP ordering so inventory can be
enabled branch by branch without rewriting the order workflow.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class StockLocation(Base):
    __tablename__ = "stock_locations"
    __table_args__ = (UniqueConstraint("branch_id", "name", name="uq_stock_locations_branch_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "name", name="uq_ingredients_restaurant_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StockThreshold(Base):
    __tablename__ = "stock_thresholds"
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "branch_id",
            "ingredient_id",
            name="uq_stock_thresholds_branch_ingredient",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False)
    warning_quantity = Column(Numeric(12, 3), nullable=False)
    critical_quantity = Column(Numeric(12, 3), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ingredient = relationship("Ingredient")


class MenuItemRecipeItem(Base):
    __tablename__ = "menu_item_recipe_items"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "ingredient_id", name="uq_recipe_menu_item_ingredient"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(
        UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=False, index=True
    )
    ingredient_id = Column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False, index=True
    )
    quantity = Column(Numeric(12, 3), nullable=False)

    ingredient = relationship("Ingredient")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    stock_location_id = Column(UUID(as_uuid=True), ForeignKey("stock_locations.id"), nullable=False)
    ingredient_id = Column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False, index=True
    )
    movement_type = Column(String, nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False)
    reference_type = Column(String, nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
