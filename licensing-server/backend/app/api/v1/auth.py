"""Authentication endpoints — login, register, refresh, logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    LoginRequest, RegisterRequest, RefreshRequest,
    LoginResponse, TokenResponse, UserResponse,
)
from app.services.auth_service import (
    authenticate_user, create_user, create_access_token,
    create_refresh_token, decode_token, hash_password,
)
from app.models.user import User

router = APIRouter(tags=["Authentication"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
    )


@router.post("/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(
            db=db,
            email=body.email,
            password=body.password,
            name=body.name,
            company=body.company,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    user_id = int(payload["sub"])
    role = payload.get("role", "customer")
    new_access = create_access_token(user_id, role)
    new_refresh = create_refresh_token(user_id)
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=30,
    )


@router.post("/auth/logout")
async def logout():
    """Client-side logout — token invalidation is handled client-side."""
    return {"message": "Logged out successfully"}
