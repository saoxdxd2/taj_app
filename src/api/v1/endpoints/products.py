"""
TAJ FROID ERP - Product Endpoints
RESTful API for product and inventory management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

from src.api.core.database import get_async_session
from src.api.core.security import get_current_user, TokenData
from src.modules.inventory.models import Product, StockMovement

router = APIRouter()


class ProductCreate(BaseModel):
    """Product creation schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    unit_price: Decimal = Field(..., ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    category: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    """Product update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    category: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[dict])
async def list_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List products with pagination and filtering"""
    query = select(Product).order_by(Product.name)
    
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    
    if category:
        query = query.where(Product.category == category)
    
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    products = result.scalars().all()
    
    return [{
        "id": prod.id,
        "name": prod.name,
        "sku": prod.sku,
        "unit_price": float(prod.unit_price),
        "category": prod.category,
        "is_active": prod.is_active
    } for prod in products]


@router.get("/{product_id}", response_model=dict)
async def get_product(
    product_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get product by ID"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "sku": product.sku,
        "unit_price": float(product.unit_price),
        "cost_price": float(product.cost_price) if product.cost_price else None,
        "category": product.category,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat() if product.created_at else None
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new product"""
    # Check if SKU already exists
    if product_data.sku:
        result = await db.execute(
            select(Product).where(Product.sku == product_data.sku)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SKU already exists"
            )
    
    product = Product(**product_data.model_dump())
    
    db.add(product)
    await db.commit()
    await db.refresh(product)
    
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "message": "Product created successfully"
    }


@router.patch("/{product_id}", response_model=dict)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update product"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    await db.commit()
    await db.refresh(product)
    
    return {
        "id": product.id,
        "message": "Product updated successfully"
    }


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete product (soft delete by deactivating)"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Soft delete
    product.is_active = False
    await db.commit()
    
    return None


@router.get("/{product_id}/stock", response_model=dict)
async def get_product_stock(
    product_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get product stock level"""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Calculate stock from movements
    movements_result = await db.execute(
        select(StockMovement).where(StockMovement.product_id == product_id)
    )
    movements = movements_result.scalars().all()
    
    total_in = sum(m.quantity for m in movements if m.movement_type == "IN")
    total_out = sum(m.quantity for m in movements if m.movement_type == "OUT")
    
    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": total_in - total_out,
        "total_in": total_in,
        "total_out": total_out
    }
