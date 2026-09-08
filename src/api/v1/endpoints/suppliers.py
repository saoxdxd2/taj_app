"""
TAJ FROID ERP - Supplier Endpoints
RESTful API for supplier management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, Field

from src.api.core.database import get_async_session
from src.api.core.security import get_current_user, TokenData
from src.modules.suppliers.models import Supplier

router = APIRouter()


class SupplierCreate(BaseModel):
    """Supplier creation schema"""
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    """Supplier update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[dict])
async def list_suppliers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List suppliers with pagination and filtering"""
    query = select(Supplier).order_by(Supplier.name)
    
    if search:
        query = query.where(Supplier.name.ilike(f"%{search}%"))
    
    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    suppliers = result.scalars().all()
    
    return [{
        "id": sup.id,
        "name": sup.name,
        "email": sup.email,
        "phone": sup.phone,
        "city": sup.city,
        "country": sup.country,
        "is_active": sup.is_active
    } for sup in suppliers]


@router.get("/{supplier_id}", response_model=dict)
async def get_supplier(
    supplier_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get supplier by ID"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    return {
        "id": supplier.id,
        "name": supplier.name,
        "email": supplier.email,
        "phone": supplier.phone,
        "address": supplier.address,
        "city": supplier.city,
        "country": supplier.country,
        "tax_id": supplier.tax_id,
        "contact_name": supplier.contact_name,
        "notes": supplier.notes,
        "is_active": supplier.is_active,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_data: SupplierCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new supplier"""
    supplier = Supplier(**supplier_data.model_dump())
    
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    
    return {
        "id": supplier.id,
        "name": supplier.name,
        "message": "Supplier created successfully"
    }


@router.patch("/{supplier_id}", response_model=dict)
async def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update supplier"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    update_data = supplier_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplier, field, value)
    
    await db.commit()
    await db.refresh(supplier)
    
    return {
        "id": supplier.id,
        "message": "Supplier updated successfully"
    }


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete supplier (soft delete by deactivating)"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found"
        )
    
    # Soft delete
    supplier.is_active = False
    await db.commit()
    
    return None
