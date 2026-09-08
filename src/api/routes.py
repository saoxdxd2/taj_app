"""FastAPI routes for products, sales, inventory, and analytics."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from src.core.database import get_db
from src.websocket.manager import manager
from src.api.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductAnalytics,
    SaleCreate, SaleResponse, DashboardAnalytics, StockUpdateMessage,
    SaleChannel, InventoryResponse
)
from src.modules.inventory.models import Product, StockLevel
from src.modules.sales.models import Invoice, InvoiceItem, SaleChannel as ModelSaleChannel
from src.modules.crm.models import Customer

router = APIRouter()


# ============== Product Routes ==============

@router.get("/products", response_model=List[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    in_stock_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get all products with optional filters."""
    query = db.query(Product)
    
    if category:
        query = query.filter(Product.category.has(name=category))
    
    if in_stock_only:
        query = query.join(StockLevel).filter(StockLevel.quantity > 0)
    
    products = query.offset(skip).limit(limit).all()
    return products


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product by ID."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/products", response_model=ProductResponse)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product."""
    # Check for duplicate SKU
    existing = db.query(Product).filter(Product.sku == product.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    db_product = Product(
        name=product.name,
        sku=product.sku,
        description=product.description,
        purchase_price=Decimal(str(product.buy_price)),
        sale_price=Decimal(str(product.buy_price)),  # Default store price = buy price
        sale_price_website=Decimal(str(product.sell_price_website)),
        vat_rate=Decimal("20.00"),
        state="Active"
    )
    
    db.add(db_product)
    db.flush()  # Get the ID
    
    # Create initial stock level
    stock_level = StockLevel(product_id=db_product.id, quantity=0, min_quantity=product.min_stock_level)
    db.add(stock_level)
    db.commit()
    db.refresh(db_product)
    
    # Broadcast to all clients
    asyncio.create_task(
        manager.broadcast_stock_update(
            product_id=db_product.id,
            product_name=db_product.name,
            old_stock=0,
            new_stock=0,
            channel="system"
        )
    )
    
    return db_product


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    """Update a product."""
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            if field in ['buy_price', 'sale_price_website']:
                setattr(db_product, field, Decimal(str(value)))
            else:
                setattr(db_product, field, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product


# ============== Sales Routes ==============

@router.post("/sales", response_model=SaleResponse)
async def create_sale(sale: SaleCreate, db: Session = Depends(get_db)):
    """
    Create a new sale (store or website).
    For store sales, allows variable sell price per item.
    For website sales, uses fixed product.sale_price_website.
    """
    # Validate channel
    channel_enum = ModelSaleChannel.STORE if sale.channel == SaleChannel.STORE else ModelSaleChannel.WEBSITE
    
    # Generate invoice number
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # Create invoice
    db_invoice = Invoice(
        invoice_number=invoice_number,
        customer_id=sale.customer_id or 1,  # Default to walk-in customer
        total_amount=Decimal("0.00"),
        channel=channel_enum,
        notes=sale.notes,
        state="Issued"
    )
    
    db.add(db_invoice)
    db.flush()
    
    total_amount = Decimal("0.00")
    
    for item in sale.items:
        # Get product
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        # Check stock
        stock = db.query(StockLevel).filter(StockLevel.product_id == item.product_id).first()
        if not stock or stock.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")
        
        # Determine unit price based on channel
        if sale.channel == SaleChannel.WEBSITE:
            unit_price = product.sale_price_website
        elif item.store_sell_price is not None:
            # Variable price for store sales
            unit_price = Decimal(str(item.store_sell_price))
        else:
            # Default to product's store price
            unit_price = product.sale_price
        
        # Calculate line total
        line_total = unit_price * item.quantity
        total_amount += line_total
        
        # Create invoice item
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=unit_price,
            vat_rate=product.vat_rate,
            unit_cost=product.purchase_price,
            warranty_months=12
        )
        db.add(db_item)
        
        # Update stock
        stock.quantity -= item.quantity
        
        # Update product analytics
        if sale.channel == SaleChannel.WEBSITE:
            product.total_sold_website += item.quantity
            product.revenue_website += line_total
        else:
            product.total_sold_store += item.quantity
            product.revenue_store += line_total
        
        # Store old stock for broadcast
        old_stock = stock.quantity + item.quantity
        new_stock = stock.quantity
    
    # Update invoice total
    db_invoice.total_amount = total_amount
    db.commit()
    db.refresh(db_invoice)
    
    # Broadcast stock updates and sale created
    for item in sale.items:
        stock = db.query(StockLevel).filter(StockLevel.product_id == item.product_id).first()
        product = db.query(Product).filter(Product.id == item.product_id).first()
        await manager.broadcast_stock_update(
            product_id=item.product_id,
            product_name=product.name,
            old_stock=old_stock,
            new_stock=stock.quantity,
            channel=sale.channel.value
        )
    
    await manager.broadcast_sale_created({
        "sale_id": db_invoice.id,
        "invoice_number": db_invoice.invoice_number,
        "total_amount": float(total_amount),
        "channel": sale.channel.value,
        "items_count": len(sale.items)
    })
    
    return db_invoice


@router.get("/sales", response_model=List[SaleResponse])
def list_sales(
    skip: int = 0,
    limit: int = 100,
    channel: Optional[SaleChannel] = None,
    db: Session = Depends(get_db)
):
    """List all sales with optional channel filter."""
    query = db.query(Invoice).filter(Invoice.state == "Issued")
    
    if channel:
        channel_enum = ModelSaleChannel.STORE if channel == SaleChannel.STORE else ModelSaleChannel.WEBSITE
        query = query.filter(Invoice.channel == channel_enum)
    
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    return invoices


# ============== Analytics Routes ==============

@router.get("/analytics/dashboard", response_model=DashboardAnalytics)
def get_dashboard_analytics(db: Session = Depends(get_db)):
    """Get comprehensive dashboard analytics for store owner."""
    # Total revenue and profit
    total_revenue = Decimal("0.00")
    total_profit = Decimal("0.00")
    total_sales = db.query(Invoice).filter(Invoice.state == "Issued").count()
    
    products = db.query(Product).all()
    
    for product in products:
        total_revenue += product.revenue_website + product.revenue_store
        # Profit = revenue - (cost * quantity sold)
        total_cost = product.purchase_price * (product.total_sold_website + product.total_sold_store)
        total_profit += (product.revenue_website + product.revenue_store) - total_cost
    
    # Low stock and out of stock
    stock_levels = db.query(StockLevel).all()
    low_stock = sum(1 for s in stock_levels if s.quantity <= s.min_quantity and s.quantity > 0)
    out_of_stock = sum(1 for s in stock_levels if s.quantity <= 0)
    
    # Top selling products
    top_products = sorted(
        products,
        key=lambda p: p.total_sold_website + p.total_sold_store,
        reverse=True
    )[:10]
    
    top_analytics = []
    for product in top_products:
        stock = db.query(StockLevel).filter(StockLevel.product_id == product.id).first()
        total_sold = product.total_sold_website + product.total_sold_store
        
        # Calculate average store sell price
        avg_store_price = None
        if product.total_sold_store > 0:
            avg_store_price = float(product.revenue_store / product.total_sold_store)
        
        # Profit margins
        margin_website = float((product.sale_price_website - product.purchase_price) / product.sale_price_website * 100) if product.sale_price_website > 0 else 0
        margin_store = None
        if avg_store_price and avg_store_price > 0:
            margin_store = float((avg_store_price - product.purchase_price) / avg_store_price * 100)
        
        analytics = ProductAnalytics(
            product_id=product.id,
            product_name=product.name,
            buy_price=float(product.purchase_price),
            sell_price_website=float(product.sale_price_website),
            avg_store_sell_price=avg_store_price,
            total_sold_website=product.total_sold_website,
            total_sold_store=product.total_sold_store,
            revenue_website=float(product.revenue_website),
            revenue_store=float(product.revenue_store),
            profit_margin_website=margin_website,
            profit_margin_store=margin_store,
            current_stock=stock.quantity if stock else 0,
            turnover_rate=float(total_sold / (stock.quantity + total_sold) * 100) if (stock.quantity + total_sold) > 0 else 0
        )
        top_analytics.append(analytics)
    
    return DashboardAnalytics(
        total_revenue=float(total_revenue),
        total_profit=float(total_profit),
        total_sales_count=total_sales,
        low_stock_products=low_stock,
        out_of_stock_products=out_of_stock,
        top_selling_products=top_analytics
    )


# ============== WebSocket Endpoint ==============

@router.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str = "all"):
    """
    WebSocket endpoint for real-time updates.
    client_type: 'all', 'inventory', 'sales', 'analytics', 'mobile_app'
    """
    await manager.connect(websocket, client_type)
    try:
        while True:
            # Keep connection alive, optionally receive messages
            data = await websocket.receive_text()
            # Could handle commands from mobile app here
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_type)
