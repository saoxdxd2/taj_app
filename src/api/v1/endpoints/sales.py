"""
TAJ FROID ERP - Sales Endpoints
RESTful API for invoices, quotations, and payments
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel

from src.api.core.database import get_async_session
from src.api.core.security import get_current_user, TokenData, require_admin
from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState, Quotation, Payment

router = APIRouter()


class InvoiceCreate(BaseModel):
    """Invoice creation schema"""
    customer_id: int
    items: List[dict]
    notes: Optional[str] = None


@router.get("/invoices", response_model=List[dict])
async def list_invoices(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """List invoices with pagination and filtering"""
    query = select(Invoice).order_by(Invoice.created_at.desc())
    
    if state:
        query = query.where(Invoice.state == state)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    invoices = result.scalars().all()
    
    return [{
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "customer_id": inv.customer_id,
        "state": inv.state,
        "total_amount": float(inv.total_amount),
        "created_at": inv.created_at.isoformat() if inv.created_at else None
    } for inv in invoices]


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Get invoice by ID with items"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Get invoice items
    items_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    )
    items = items_result.scalars().all()
    
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "state": invoice.state,
        "total_amount": float(invoice.total_amount),
        "notes": invoice.notes,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "items": [{
            "id": item.id,
            "product_id": item.product_id,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "total": float(item.total)
        } for item in items]
    }


@router.post("/invoices", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: dict,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new invoice"""
    # Generate invoice number
    now = datetime.now(timezone.utc)
    yy = f"{now.year % 100:02d}"
    suffix = f"-{yy}"
    
    result = await db.execute(
        select(Invoice.invoice_number).where(
            Invoice.invoice_number.like(f"N°%{suffix}")
        )
    )
    existing_numbers = result.scalars().all()
    
    max_seq = 0
    for number in existing_numbers:
        middle = number[2:-len(suffix)]
        if middle.isdigit():
            max_seq = max(max_seq, int(middle))
    
    invoice_number = f"N°{max_seq + 1:02d}-{yy}"
    
    # Create invoice
    invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=invoice_data["customer_id"],
        state=InvoiceState.DRAFT,
        total_amount=Decimal("0"),
        notes=invoice_data.get("notes")
    )
    
    db.add(invoice)
    await db.flush()
    
    # Add items
    total = Decimal("0")
    for item_data in invoice_data.get("items", []):
        quantity = Decimal(str(item_data["quantity"]))
        unit_price = Decimal(str(item_data["unit_price"]))
        item_total = quantity * unit_price
        
        item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=item_data["product_id"],
            quantity=quantity,
            unit_price=unit_price,
            total=item_total
        )
        db.add(item)
        total += item_total
    
    invoice.total_amount = total
    await db.commit()
    await db.refresh(invoice)
    
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "message": "Invoice created successfully"
    }


@router.patch("/invoices/{invoice_id}/state", response_model=dict)
async def update_invoice_state(
    invoice_id: int,
    new_state: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """Update invoice state"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Validate state transition
    valid_states = [s.value for s in InvoiceState]
    if new_state not in valid_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state. Must be one of: {valid_states}"
        )
    
    invoice.state = new_state
    await db.commit()
    
    return {
        "id": invoice.id,
        "state": invoice.state,
        "message": "Invoice state updated successfully"
    }


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: int,
    current_user: TokenData = Depends(require_admin()),
    db: AsyncSession = Depends(get_async_session)
):
    """Delete an invoice (admin only)"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Only draft invoices can be deleted
    if invoice.state != InvoiceState.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft invoices can be deleted"
        )
    
    await db.delete(invoice)
    await db.commit()
    
    return None
