"""Central SQLAlchemy model registry.

Import this module before using ORM relationships so SQLAlchemy can resolve
string-based relationship targets across modules.
"""

from app.audit.models import AuditLog
from app.auth.models import PasswordResetToken, Role, User, user_branches
from app.customers.models import Customer
from app.incidents.models import PlatformIncident
from app.inventory.models import (
    Ingredient,
    MenuItemRecipeItem,
    StockLocation,
    StockMovement,
    StockThreshold,
)
from app.menu.models import MenuCategory, MenuItem
from app.orders.models import Order, OrderItem, OrderStatusHistory
from app.payments.models import Payment, PaymentEvent
from app.tenants.models import Branch, Restaurant, RestaurantSettings

__all__ = [
    "AuditLog",
    "Branch",
    "Customer",
    "Ingredient",
    "MenuCategory",
    "MenuItem",
    "MenuItemRecipeItem",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Payment",
    "PaymentEvent",
    "PasswordResetToken",
    "PlatformIncident",
    "Restaurant",
    "RestaurantSettings",
    "Role",
    "StockLocation",
    "StockMovement",
    "StockThreshold",
    "User",
    "user_branches",
]
