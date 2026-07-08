"""Machine model — registered device fingerprints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    operating_system: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cpu_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    motherboard_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disk_serial: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bios_uuid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mac_address_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    activations: Mapped[List["LicenseActivation"]] = relationship("LicenseActivation", back_populates="machine", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Machine id={self.id} fingerprint={self.fingerprint_hash[:16]!r}>"
