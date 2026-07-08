#!/usr/bin/env python3
"""Initialize the database — create tables and seed with default data."""
import asyncio
import secrets
import logging
from app.database import engine, async_session_factory, Base
from app.models import *  # noqa
from app.models.user import User, UserRole
from app.models.product import Product
from app.services.auth_service import hash_password
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created.")

    async with async_session_factory() as session:
        # Seed products
        products = [
            {"code": "HARPER", "name": "Harper AI", "version": "1.1.0"},
            {"code": "STRATUM", "name": "Stratum Trading Strategy Analyzer", "version": "1.2.0"},
            {"code": "AI_TSA", "name": "AI Trading Strategy Analyzer", "version": "1.0.0"},
            {"code": "BACKTESTING_BOT", "name": "Backtesting Bot", "version": "1.0.0"},
            {"code": "CONQUEST", "name": "Conquest Trading Engine", "version": "2.0.0"},
        ]
        for p in products:
            result = await session.execute(select(Product).where(Product.code == p["code"]))
            if not result.scalar_one_or_none():
                session.add(Product(code=p["code"], name=p["name"], version=p["version"], active=True))
                logger.info(f"  Created product: {p['code']}")

        # Seed super admin
        result = await session.execute(select(User).where(User.email == "admin@wovenmodel.com"))
        if not result.scalar_one_or_none():
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
            print("\n" + "=" * 60)
            print("SUPER ADMIN CREDENTIALS (save these):")
            print(f"  Email:    admin@wovenmodel.com")
            print(f"  Password: {admin_password}")
            print("=" * 60 + "\n")
        else:
            logger.info("  Super admin already exists.")

        await session.commit()

    await engine.dispose()
    logger.info("Database initialized successfully.")


if __name__ == "__main__":
    asyncio.run(init())
