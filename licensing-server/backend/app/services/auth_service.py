"""Authentication service — password hashing, JWT tokens, login/logout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, role: str) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns None if invalid."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.now(timezone.utc)
    return user


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
    company: Optional[str] = None,
    role: UserRole = UserRole.CUSTOMER,
) -> User:
    """Create a new user."""
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError(f"User with email {email!r} already exists")

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        company=company,
        role=role,
    )
    db.add(user)
    await db.flush()
    return user
