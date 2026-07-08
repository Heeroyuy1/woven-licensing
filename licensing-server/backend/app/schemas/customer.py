"""Pydantic schemas for customer portal endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    id: int
    email: str
    name: str
    company: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None


class CustomerLicenseResponse(BaseModel):
    id: int
    license_key: str
    license_type: str
    status: str
    product_code: str
    product_name: str
    expiration_date: Optional[datetime] = None
    perpetual: bool
    max_activations: int
    current_activations: int
    offline_days: int
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerActivationResponse(BaseModel):
    id: int
    machine_fingerprint: str
    machine_hostname: Optional[str] = None
    machine_os: Optional[str] = None
    status: str
    activation_date: datetime
    last_validation: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerMachineResponse(BaseModel):
    id: int
    fingerprint_hash: str
    hostname: Optional[str] = None
    operating_system: Optional[str] = None
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True
