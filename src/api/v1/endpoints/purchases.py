"""
TAJ FROID ERP - Purchase Endpoints
RESTful API for purchase orders management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from src.api.core.database import get_async_session
from src.api.core.security import get_current_user, TokenData
from src.modules.purchasing.models import Purchase, PurchaseItem, PurchaseState

router = APIRouter()


class PurchaseCreate(BaseModel):
    """Purchase order creation schema"""
    supplier_id: int
    items: List[dict]
    expected_date: Optional[str] = None
    notes: Optional[str] = None


@router.get("", response_model=List[dict])
async def list_purchases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List purchase orders with pagination and filtering"""
    query = select(Purchase).order_by(Purchase.created_at.desc())
    
    if state:
        query = query.where(Purchase.state == state)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    purchases = result.scalars().all()
    
    return [{
        "id": po.id,
        "reference": po.reference,
        "supplier_id": po.supplier_id,
        "state": po.state,
        "total_amount": float(po.total_amount),
        "created_at": po.created_at.isoformat() if po.created_at else None
    } for po in purchases]


@router.get("/{purchase_id}", response_model=dict)
async def get_purchase(
    purchase_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get purchase order by ID"""
    result = await db.execute(
        select(Purchase).where(Purchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    
    # Get items
    items_result = await db.execute(
        select(PurchaseItem).where(PurchaseItem.purchase_id == purchase_id)
    )
    items = items_result.scalars().all()
    
    return {
        "id": purchase.id,
        "reference": purchase.reference,
        "supplier_id": purchase.supplier_id,
        "state": purchase.state,
        "total_amount": float(purchase.total_amount),
        "notes": purchase.notes,
        "expected_date": purchase.expected_date.isoformat() if purchase.expected_date else None,
        "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
        "items": [{
            "id": item.id,
            "product_id": item.product_id,
            "quantity": float(item.quantity),
            "unit_cost": float(item.unit_cost),
            "total": float(item.total)
        } for item in items]
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    purchase_data: PurchaseCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new purchase order"""
    # Generate order number
    now = datetime.now(timezone.utc)
    yy = f"{now.year % 100:02d}"
    
    result = await db.execute(
        select(Purchase.reference).where(
            Purchase.reference.like(f"PO-%{yy}")
        )
    )
    existing_numbers = result.scalars().all()
    
    max_seq = 0
    for number in existing_numbers:
        seq_part = number.split("-")[1]
        if seq_part.isdigit():
            max_seq = max(max_seq, int(seq_part))
    
    reference = f"PO-{max_seq + 1:04d}-{yy}"
    
    # Create purchase order
    purchase = Purchase(
        reference=reference,
        supplier_id=purchase_data.supplier_id,
        state=PurchaseState.DRAFT,
        total_amount=Decimal("0"),
        notes=purchase_data.notes
    )
    
    if purchase_data.expected_date:
        from datetime import date
        purchase.expected_date = date.fromisoformat(purchase_data.expected_date)
    
    db.add(purchase)
    await db.flush()
    
    # Add items
    total = Decimal("0")
    for item_data in purchase_data.items:
        quantity = Decimal(str(item_data["quantity"]))
        unit_cost = Decimal(str(item_data["unit_cost"]))
        item_total = quantity * unit_cost
        
        item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=item_data["product_id"],
            quantity=quantity,
            unit_cost=unit_cost,
            total=item_total
        )
        db.add(item)
        total += item_total
    
    purchase.total_amount = total
    await db.commit()
    await db.refresh(purchase)
    
    return {
        "id": purchase.id,
        "reference": purchase.reference,
        "message": "Purchase order created successfully"
    }


@router.patch("/{purchase_id}/state", response_model=dict)
async def update_purchase_state(
    purchase_id: int,
    new_state: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update purchase order state"""
    result = await db.execute(
        select(Purchase).where(Purchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    
    valid_states = [s.value for s in PurchaseState]
    if new_state not in valid_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state. Must be one of: {valid_states}"
        )
    
    purchase.state = new_state
    await db.commit()
    
    return {
        "id": purchase.id,
        "state": purchase.state,
        "message": "Purchase order state updated successfully"
    }


@router.delete("/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase(
    purchase_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete purchase order (only drafts)"""
    result = await db.execute(
        select(Purchase).where(Purchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()
    
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found"
        )
    
    if purchase.state != PurchaseState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft purchase orders can be deleted"
        )
    
    await db.delete(purchase)
    await db.commit()
    
    return None
