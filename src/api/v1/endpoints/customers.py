"""
TAJ FROID ERP - Customer Endpoints
RESTful API for customer management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

from src.api.core.database import get_async_session
from src.api.core.security import get_current_user, TokenData
from src.modules.crm.models import Customer

router = APIRouter()


class CustomerCreate(BaseModel):
    """Customer creation schema"""
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Customer update schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[dict])
async def list_customers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List customers with pagination and filtering"""
    query = select(Customer).order_by(Customer.name)
    
    if search:
        query = query.where(Customer.name.ilike(f"%{search}%"))
    
    if is_active is not None:
        query = query.where(Customer.is_active == is_active)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    customers = result.scalars().all()
    
    return [{
        "id": cust.id,
        "name": cust.name,
        "email": cust.email,
        "phone": cust.phone,
        "city": cust.city,
        "country": cust.country,
        "is_active": cust.is_active
    } for cust in customers]


@router.get("/{customer_id}", response_model=dict)
async def get_customer(
    customer_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get customer by ID"""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "city": customer.city,
        "country": customer.country,
        "tax_id": customer.tax_id,
        "notes": customer.notes,
        "is_active": customer.is_active,
        "created_at": customer.created_at.isoformat() if customer.created_at else None
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new customer"""
    customer = Customer(**customer_data.model_dump())
    
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    
    return {
        "id": customer.id,
        "name": customer.name,
        "message": "Customer created successfully"
    }


@router.patch("/{customer_id}", response_model=dict)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update customer"""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    
    return {
        "id": customer.id,
        "message": "Customer updated successfully"
    }


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete customer (soft delete by deactivating)"""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Soft delete
    customer.is_active = False
    await db.commit()
    
    return None
