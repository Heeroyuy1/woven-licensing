"""Pydantic schemas for admin operations."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr, Field


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str
    role: str = "customer"
    company: Optional[str] = None


class AdminUpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    company: Optional[str] = None


class AdminGenerateLicenseRequest(BaseModel):
    product_code: str
    user_id: int
    license_type: str = "perpetual"
    max_activations: int = 1
    max_devices: int = 1
    expiration_days: Optional[int] = None
    perpetual: bool = False
    offline_days: int = 7
    feature_flags: Optional[List[str]] = None
    notes: Optional[str] = None


class AdminRevokeLicenseRequest(BaseModel):
    reason: str = "Revoked by admin"


class AdminUserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    company: Optional[str] = None
    email_verified: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    license_count: int = 0

    class Config:
        from_attributes = True


class AdminLicenseResponse(BaseModel):
    id: int
    license_key: str
    license_type: str
    status: str
    product_code: str
    user_email: str
    user_name: str
    max_activations: int
    current_activations: int
    expiration_date: Optional[datetime] = None
    perpetual: bool
    created_at: datetime
    activation_count: int = 0

    class Config:
        from_attributes = True


class AdminMachineResponse(BaseModel):
    id: int
    fingerprint_hash: str
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    is_blacklisted: bool
    first_seen: datetime
    last_seen: datetime
    activation_count: int = 0

    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    total_users: int = 0
    total_licenses: int = 0
    active_licenses: int = 0
    total_machines: int = 0
    total_activations: int = 0
    total_products: int = 0
    licenses_by_type: Dict[str, int] = {}
    licenses_by_status: Dict[str, int] = {}
    recent_activations_24h: int = 0


class AdminLogEntry(BaseModel):
    id: int
    timestamp: datetime
    action: str
    user_email: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    success: bool
    details: Optional[str] = None

    class Config:
        from_attributes = True


class AdminExportResponse(BaseModel):
    export_type: str
    record_count: int
    filename: str
    data: List[Dict[str, Any]]
