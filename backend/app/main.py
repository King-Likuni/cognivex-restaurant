from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import app.models  # noqa: F401
from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.observability import configure_logging, request_logging_middleware
from app.inventory.router import router as inventory_router
from app.kitchen.router import router as kitchen_router
from app.menu.router import router as menu_router
from app.orders.router import router as orders_router
from app.payments.router import router as payments_router
from app.payments.router import webhook_router as payment_webhook_router
from app.public.router import router as public_router
from app.realtime.router import router as realtime_router
from app.reports.router import router as reports_router
from app.tenants.router import router as tenants_router

configure_logging(settings.LOG_LEVEL)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

app.middleware("http")(request_logging_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/ready")
def readiness_check(response: Response):
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unavailable"}
    return {"status": "ready", "database": "ok"}


app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(tenants_router, prefix=settings.API_V1_STR)
app.include_router(menu_router, prefix=settings.API_V1_STR)
app.include_router(inventory_router, prefix=settings.API_V1_STR)
app.include_router(orders_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(payment_webhook_router, prefix=settings.API_V1_STR)
app.include_router(kitchen_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(public_router, prefix=settings.API_V1_STR)
app.include_router(realtime_router)
