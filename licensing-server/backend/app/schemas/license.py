"""Pydantic schemas for license activation, validation, and management."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class ActivateRequest(BaseModel):
    license_key: str = Field(..., description="License key in XXXXX-XXXXX-XXXXX-XXXXX format")
    fingerprint_data: Optional[Dict[str, Any]] = Field(None, description="Machine hardware identifiers (dict)")
    fingerprint: Optional[str] = Field(None, description="Pre-computed fingerprint hash string")
    ip_address: Optional[str] = None
    application_version: Optional[str] = None


class ValidateRequest(BaseModel):
    license_key: str
    fingerprint: str
    signature: Optional[str] = Field(None, description="Optional offline signed certificate for offline validation")


class DeactivateRequest(BaseModel):
    license_key: str
    fingerprint: str


class TransferRequest(BaseModel):
    license_key: str
    old_fingerprint: str
    new_fingerprint_data: Dict[str, Any]


class CertificateData(BaseModel):
    license_key: str
    license_type: str
    status: str
    product_id: int
    user_id: int
    expiration_date: Optional[str] = None
    perpetual: bool
    offline_days: int
    max_activations: int
    current_activations: int
    feature_flags: list = []
    machine_fingerprint: str
    machine_hostname: Optional[str] = None
    activation_date: str
    last_validation: str
    metadata: dict = {}
    issued_by: str


class ActivateResponse(BaseModel):
    success: bool
    message: str = ""
    certificate: Optional[Dict[str, Any]] = Field(None, description="Signed license certificate with signature")


class ValidateResponse(BaseModel):
    valid: bool
    message: str
    certificate: Optional[Dict[str, Any]] = None


class DeactivateResponse(BaseModel):
    success: bool
    message: str


class TransferResponse(BaseModel):
    success: bool
    message: str
    certificate: Optional[Dict[str, Any]] = None


class RenewRequest(BaseModel):
    license_id: int
    extra_days: int = 365


class CheckUpdatesResponse(BaseModel):
    update_available: bool
    latest_version: str = "1.0.0"
    download_url: str = ""
    release_notes: str = ""
    force_update: bool = False


class LicenseInfoResponse(BaseModel):
    id: int
    license_key: str
    license_type: str
    status: str
    product_id: int
    user_id: int
    expiration_date: Optional[datetime] = None
    max_activations: int
    current_activations: int
    perpetual: bool
    offline_days: int
    feature_flags: Optional[str] = None
    created_at: datetime
    activations: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True
