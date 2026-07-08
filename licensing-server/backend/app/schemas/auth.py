"""Pydantic schemas for authentication endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    name: str
    role: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    company: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
