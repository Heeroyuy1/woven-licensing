"""Product listing endpoints — available for authenticated and unauthenticated users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_admin
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/")
async def list_products(db: AsyncSession = Depends(get_db)):
    """List all active products."""
    result = await db.execute(select(Product).where(Product.active == True).order_by(Product.name))
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "code": p.code,
            "version": p.version,
            "description": p.description,
        }
        for p in products
    ]


@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": product.id,
        "name": product.name,
        "code": product.code,
        "version": product.version,
        "description": product.description,
        "active": product.active,
        "metadata_json": product.metadata_json,
        "created_at": product.created_at.isoformat(),
    }
