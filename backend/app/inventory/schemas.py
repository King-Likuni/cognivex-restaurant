"""Pydantic schemas for inventory and recipe workflows."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.inventory.enums import StockMovementType


class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    unit: str = Field(..., min_length=1, max_length=40)


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=40)


class IngredientResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    name: str
    unit: str

    model_config = {"from_attributes": True}


class StockLocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class StockLocationResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    branch_id: UUID
    name: str

    model_config = {"from_attributes": True}


class RecipeItemCreate(BaseModel):
    ingredient_id: UUID
    quantity: Decimal = Field(..., gt=Decimal("0.000"), max_digits=12, decimal_places=3)


class RecipeItemUpdate(BaseModel):
    quantity: Decimal = Field(..., gt=Decimal("0.000"), max_digits=12, decimal_places=3)


class RecipeItemResponse(BaseModel):
    id: UUID
    menu_item_id: UUID
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    quantity: Decimal


class StockMovementCreate(BaseModel):
    stock_location_id: UUID
    ingredient_id: UUID
    movement_type: StockMovementType
    quantity: Decimal = Field(..., max_digits=12, decimal_places=3)

    @model_validator(mode="after")
    def validate_signed_quantity(self) -> "StockMovementCreate":
        if self.movement_type == StockMovementType.RECEIVED and self.quantity <= 0:
            raise ValueError("Received stock quantity must be positive")
        if self.movement_type == StockMovementType.ADJUSTMENT and self.quantity == 0:
            raise ValueError("Stock adjustment quantity cannot be zero")
        if self.movement_type == StockMovementType.WASTAGE and self.quantity >= 0:
            raise ValueError("Wastage quantity must be negative")
        if self.movement_type == StockMovementType.ORDER_CONSUMPTION:
            raise ValueError("Order consumption movements are created by the order workflow")
        return self


class StockMovementResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    branch_id: UUID
    stock_location_id: UUID
    ingredient_id: UUID
    movement_type: str
    quantity: Decimal
    reference_type: str | None
    reference_id: UUID | None
    created_by: UUID | None

    model_config = {"from_attributes": True}


class StockBalanceResponse(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    quantity_on_hand: Decimal
