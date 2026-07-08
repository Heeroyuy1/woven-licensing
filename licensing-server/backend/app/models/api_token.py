"""API Token model — for programmatic access to the licensing API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    permissions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON array of granted scopes")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="api_tokens", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ApiToken id={self.id} name={self.name!r}>"
