"""License model — license keys, types, and status."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Boolean, Text, DateTime, Enum as SAEnum, Float, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LicenseType(str, enum.Enum):
    TRIAL = "trial"
    PERPETUAL = "perpetual"
    SUBSCRIPTION = "subscription"
    DEVELOPER = "developer"
    ENTERPRISE = "enterprise"
    FLOATING = "floating"
    OFFLINE = "offline"
    TIME_LIMITED = "time_limited"
    OEM = "oem"
    ACADEMIC = "academic"
    INTERNAL = "internal"


class LicenseStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    PENDING = "pending"


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    license_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    license_type: Mapped[LicenseType] = mapped_column(SAEnum(LicenseType), default=LicenseType.PERPETUAL, nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(SAEnum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    max_activations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_devices: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_activations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    perpetual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    offline_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False, comment="Days allowed offline without validation")
    feature_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON list of enabled features")
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Custom metadata")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="licenses", lazy="selectin")
    user: Mapped["User"] = relationship("User", back_populates="licenses", lazy="selectin")
    activations: Mapped[List["LicenseActivation"]] = relationship("LicenseActivation", back_populates="license", lazy="selectin", cascade="all, delete-orphan")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="license", lazy="selectin", uselist=False)

    def __repr__(self) -> str:
        return f"<License id={self.id} key={self.license_key[:12]!r} type={self.license_type.value} status={self.status.value}>"
