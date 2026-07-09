"""
Woven Model Universal Licensing Platform — FastAPI Application Entry Point

Provides license activation, validation, machine binding, customer portal,
admin dashboard, and product update-check endpoints.
"""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.config import settings
from app.database import engine, async_session_factory, Base
from app.models.user import User, UserRole
from app.models.product import Product
from app.services.auth_service import hash_password
from app.api.v1 import api_router

logger = logging.getLogger("licensing-server")


def _create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router)

    # Serve licensing portal static files
    portal_dir = Path(__file__).resolve().parent.parent / "portal"
    if portal_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(portal_dir), html=True), name="portal")
        logger.info(f"Serving portal from {portal_dir}")
    else:
        logger.warning(f"Portal directory not found: {portal_dir}")

    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan — create tables and seed data on startup."""
    logger.info("Starting Woven Model Licensing Server...")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    # Seed default data
    async with async_session_factory() as session:
        await _seed_products(session)
        await _seed_admin(session)
        await session.commit()
    logger.info("Seed data verified.")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Licensing Server shut down.")


app = _create_app()


async def _seed_products(session):
    """Ensure default products exist."""
    defaults = [
        {"code": "HARPER", "name": "Harper AI", "version": "1.1.0"},
        {"code": "STRATUM", "name": "Stratum Trading Strategy Analyzer", "version": "1.2.0"},
        {"code": "AI_TSA", "name": "AI Trading Strategy Analyzer", "version": "1.0.0"},
        {"code": "BACKTESTING_BOT", "name": "Backtesting Bot", "version": "1.0.0"},
        {"code": "CONQUEST", "name": "Conquest Trading Engine", "version": "2.0.0"},
    ]
    for prod in defaults:
        result = await session.execute(select(Product).where(Product.code == prod["code"]))
        existing = result.scalar_one_or_none()
        if not existing:
            session.add(Product(
                code=prod["code"],
                name=prod["name"],
                version=prod["version"],
                active=True,
            ))
            logger.info(f"  Created product: {prod['code']}")
        else:
            logger.debug(f"  Product exists: {prod['code']}")


async def _seed_admin(session):
    """Ensure a super admin user exists."""
    result = await session.execute(select(User).where(User.email == "admin@wovenmodel.com"))
    admin = result.scalar_one_or_none()
    if not admin:
        admin_password = secrets.token_urlsafe(12)
        admin = User(
            email="admin@wovenmodel.com",
            password_hash=hash_password(admin_password),
            name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            email_verified=True,
        )
        session.add(admin)
        await session.flush()
        logger.info(f"  Created super admin: admin@wovenmodel.com / {admin_password}")
        print("=" * 60)
        print(f"SUPER ADMIN CREDENTIALS (save these):")
        print(f"  Email:    admin@wovenmodel.com")
        print(f"  Password: {admin_password}")
        print("=" * 60)
    else:
        logger.debug("  Super admin exists: admin@wovenmodel.com")


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    db_ok = False
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")

    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "disconnected",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global catch-all exception handler."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
