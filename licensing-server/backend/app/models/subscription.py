"""Subscription model — recurring billing and renewal tracking."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, func, ForeignKey, Enum as SAEnum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class BillingCycle(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    BI_YEARLY = "bi_yearly"
    ONE_TIME = "one_time"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    billing_cycle: Mapped[BillingCycle] = mapped_column(SAEnum(BillingCycle), default=BillingCycle.MONTHLY, nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    renewal_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="stripe, paypal, etc.")
    payment_provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Provider subscription ID")
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    license: Mapped["License"] = relationship("License", back_populates="subscription", lazy="selectin")
    user: Mapped["User"] = relationship("User", back_populates="subscriptions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} cycle={self.billing_cycle.value} status={self.payment_status.value}>"
