"""User model — authentication and role-based access."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Enum, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    DEVELOPER = "developer"
    SUPPORT = "support"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    licenses: Mapped[List["License"]] = relationship("License", back_populates="user", lazy="selectin")
    subscriptions: Mapped[List["Subscription"]] = relationship("Subscription", back_populates="user", lazy="selectin")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user", lazy="selectin")
    api_tokens: Mapped[List["ApiToken"]] = relationship("ApiToken", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
