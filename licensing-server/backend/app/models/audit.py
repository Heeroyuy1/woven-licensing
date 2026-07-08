"""Audit Log model — immutable record of all system actions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, func, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    product_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON metadata about the action")

    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r} success={self.success}>"
