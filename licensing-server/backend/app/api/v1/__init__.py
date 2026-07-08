"""API v1 router package."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.licensing import router as licensing_router
from app.api.v1.admin import router as admin_router
from app.api.v1.customer import router as customer_router
from app.api.v1.products import router as products_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(licensing_router)
api_router.include_router(admin_router)
api_router.include_router(customer_router)
api_router.include_router(products_router)

__all__ = ["api_router"]
