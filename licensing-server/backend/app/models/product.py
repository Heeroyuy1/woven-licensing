"""Product model — products that can be licensed."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON blob for extensible metadata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    licenses: Mapped[List["License"]] = relationship("License", back_populates="product", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Product id={self.id} code={self.code!r} name={self.name!r}>"
