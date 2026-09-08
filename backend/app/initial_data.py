"""Seed initial data like roles and an admin user."""

import logging

import app.models  # noqa: F401
from app.auth.schemas import UserCreate
from app.auth.service import create_user, seed_roles
from app.core.config import settings
from app.core.database import SessionLocal
from app.tenants.schemas import BranchCreate, RestaurantCreate
from app.tenants.service import create_branch, create_restaurant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    db = SessionLocal()
    try:
        logger.info("Seeding roles...")
        seed_roles(db)

        # Check if admin already exists
        from app.auth.models import User

        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        if not admin:
            logger.info("Creating initial platform admin...")
            create_user(
                db,
                UserCreate(
                    email=settings.INITIAL_ADMIN_EMAIL,
                    password=settings.INITIAL_ADMIN_PASSWORD,
                    first_name="Platform",
                    last_name="Admin",
                    role_name="ADMIN",
                ),
            )

        if not settings.ENABLE_SAMPLE_DATA:
            logger.info("Sample restaurant data disabled.")
            return

        # Create a sample restaurant for testing
        from app.tenants.models import Restaurant

        sample_restaurant = db.query(Restaurant).filter(Restaurant.name == "Chicken Spot").first()
        if not sample_restaurant:
            logger.info("Creating sample restaurant 'Chicken Spot'...")
            restaurant = create_restaurant(db, RestaurantCreate(name="Chicken Spot"))

            logger.info("Creating sample branch 'Main Mall'...")
            create_branch(db, restaurant.id, BranchCreate(name="Main Mall", location="Gaborone"))

            logger.info("Creating owner for 'Chicken Spot'...")
            create_user(
                db,
                UserCreate(
                    email=settings.INITIAL_OWNER_EMAIL,
                    password=settings.INITIAL_OWNER_PASSWORD,
                    first_name="Chicken",
                    last_name="Owner",
                    role_name="OWNER",
                    restaurant_id=restaurant.id,
                ),
            )

        logger.info("Initial data seeded.")
    except Exception:
        logger.exception("Error seeding data")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init()
