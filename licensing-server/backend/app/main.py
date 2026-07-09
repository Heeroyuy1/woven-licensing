"""
Woven Model Universal Licensing Platform — FastAPI Application Entry Point

Provides license activation, validation, machine binding, customer portal,
admin dashboard, and product update-check endpoints.
"""
from __future__ import annotations

import os
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

    # Serve licensing portal SPA at root
    PORTAL_DIR = Path(__file__).resolve().parent.parent / "portal"
    PORTAL_INDEX = PORTAL_DIR / "index.html"

    @app.get("/login.html")
    async def portal_login():
        login_file = PORTAL_DIR / "login.html"
        if login_file.exists():
            return FileResponse(str(login_file))
        return JSONResponse(status_code=404, content={"detail": "login.html not found"})

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

    @app.get("/")
    @app.get("/{full_path:path}")
    async def serve_portal(full_path: str = ""):
        """Serve SPA — API routes are checked first, so only non-API paths reach here."""
        # Serve static file if it exists
        if full_path:
            file_path = PORTAL_DIR / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
        # SPA fallback to index.html
        if PORTAL_INDEX.exists():
            return FileResponse(str(PORTAL_INDEX))
        return JSONResponse(status_code=404, content={"detail": "Portal not built"})

    if PORTAL_DIR.is_dir():
        logger.info(f"Serving portal from {PORTAL_DIR}")
    else:
        logger.warning(f"Portal directory not found: {PORTAL_DIR}")

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
        {"code": "PII_REMOVER", "name": "Woven Model PII Remover", "version": "1.0.0"},
        {"code": "JEEVES", "name": "Woven Model Jeeves", "version": "1.0.0"},
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
    """Ensure a super admin user exists with the configured password.

    ALWAYS updates the password from ADMIN_PASSWORD env var on every startup.
    This ensures Railway environment changes take effect immediately.
    """
    result = await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
    admin = result.scalar_one_or_none()

    # ── Direct print debugging (logger.info doesn't show in Railway logs) ──
    print("[DEBUG] ======= _seed_admin debug start =======")
    print(f"[DEBUG] ADMIN_EMAIL = {settings.ADMIN_EMAIL}")
    print(f"[DEBUG] os.environ.get('ADMIN_PASSWORD') = {os.environ.get('ADMIN_PASSWORD', 'NOT SET')}")
    print(f"[DEBUG] os.environ.get('admin_password') = {os.environ.get('admin_password', 'NOT SET')}")
    print(f"[DEBUG] settings.ADMIN_PASSWORD = {settings.ADMIN_PASSWORD}")
    print(f"[DEBUG] settings.admin_password_resolved = {settings.admin_password_resolved}")
    all_env_keys = [k for k in os.environ.keys() if 'PASS' in k.upper() or 'ADMIN' in k.upper()]
    print(f"[DEBUG] Matching env vars: {all_env_keys}")
    print("[DEBUG] ======= _seed_admin debug end =========")

    raw_password = os.environ.get("ADMIN_PASSWORD")
    if not raw_password:
        raw_password = os.environ.get("admin_password")
    if not raw_password:
        raw_password = settings.admin_password_resolved

    if raw_password:
        admin_password = raw_password
        print(f"[DEBUG] Using env var password: {admin_password[:3]}***{admin_password[-3:]}")
    else:
        admin_password = secrets.token_urlsafe(12)
        print(f"[DEBUG] No env var set - generated random password")

    if not admin:
        admin = User(
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(admin_password),
            name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            email_verified=True,
        )
        session.add(admin)
        await session.flush()
        print(f"[DEBUG] Created new admin user")
    else:
        admin.password_hash = hash_password(admin_password)
        print(f"[DEBUG] Updated existing admin password")

    await session.flush()
    print("=" * 60)
    print(f"SUPER ADMIN CREDENTIALS:")
    print(f"  Email:    {settings.ADMIN_EMAIL}")
    print(f"  Password: {admin_password}")
    print("=" * 60)


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
