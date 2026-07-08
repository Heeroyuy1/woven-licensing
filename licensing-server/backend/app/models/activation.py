"""License Activation model — records of license-to-machine bindings."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, func, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ActivationStatus(str, enum.Enum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class LicenseActivation(Base):
    __tablename__ = "license_activations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False, index=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), nullable=False, index=True)
    status: Mapped[ActivationStatus] = mapped_column(SAEnum(ActivationStatus), default=ActivationStatus.ACTIVE, nullable=False)
    activation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_validation: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    application_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    certificate_signed: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Signed offline validation certificate")

    license: Mapped["License"] = relationship("License", back_populates="activations", lazy="selectin")
    machine: Mapped["Machine"] = relationship("Machine", back_populates="activations", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Activation id={self.id} license_id={self.license_id} machine_id={self.machine_id} status={self.status.value}>"
