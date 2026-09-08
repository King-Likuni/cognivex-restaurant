"""Inventory movement values used by stock services and API payloads."""

from enum import StrEnum


class StockMovementType(StrEnum):
    RECEIVED = "RECEIVED"
    ADJUSTMENT = "ADJUSTMENT"
    WASTAGE = "WASTAGE"
    ORDER_CONSUMPTION = "ORDER_CONSUMPTION"
