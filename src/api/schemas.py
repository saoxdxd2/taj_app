"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SaleChannel(str, Enum):
    """Sales channel enumeration."""
    WEBSITE = "website"
    STORE = "store"
    MOBILE_APP = "mobile_app"


# Product Schemas
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    buy_price: float = Field(..., gt=0)
    sell_price_website: float = Field(..., gt=0, description="Fixed price for website sales")
    category: Optional[str] = None
    min_stock_level: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    name: Optional[str] = None
    description: Optional[str] = None
    buy_price: Optional[float] = None
    sell_price_website: Optional[float] = None
    category: Optional[str] = None
    min_stock_level: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Schema for product response with additional fields."""
    id: int
    current_stock: int = 0
    total_sold_website: int = 0
    total_sold_store: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True


# Inventory Schemas
class InventoryAdjustmentBase(BaseModel):
    product_id: int
    quantity_change: int
    reason: str = Field(..., min_length=1, max_length=200)
    channel: SaleChannel = SaleChannel.STORE


class InventoryAdjustmentCreate(InventoryAdjustmentBase):
    pass


class InventoryResponse(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    reserved_stock: int
    available_stock: int
    last_updated: datetime
    
    class Config:
        from_attributes = True


# Sales Schemas
class SaleItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    channel: SaleChannel = SaleChannel.STORE
    store_sell_price: Optional[float] = Field(None, gt=0, description="Variable price for store sales")


class SaleCreate(BaseModel):
    """Schema for creating a sale."""
    items: List[SaleItemBase]
    customer_id: Optional[int] = None
    notes: Optional[str] = None
    channel: SaleChannel = SaleChannel.STORE


class SaleItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    channel: SaleChannel
    
    class Config:
        from_attributes = True


class SaleResponse(BaseModel):
    id: int
    items: List[SaleItemResponse]
    total_amount: float
    channel: SaleChannel
    customer_id: Optional[int]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Analytics Schemas
class ProductAnalytics(BaseModel):
    """Analytics data for a product."""
    product_id: int
    product_name: str
    buy_price: float
    sell_price_website: float
    avg_store_sell_price: Optional[float]
    total_sold_website: int
    total_sold_store: int
    revenue_website: float
    revenue_store: float
    profit_margin_website: float
    profit_margin_store: Optional[float]
    current_stock: int
    turnover_rate: float


class DashboardAnalytics(BaseModel):
    """Dashboard analytics summary."""
    total_revenue: float
    total_profit: float
    total_sales_count: int
    low_stock_products: int
    out_of_stock_products: int
    top_selling_products: List[ProductAnalytics]


# WebSocket Message Schemas
class WSMessage(BaseModel):
    """WebSocket message structure."""
    type: str  # 'stock_update', 'sale_created', 'analytics_update'
    data: dict
    timestamp: datetime


class StockUpdateMessage(WSMessage):
    """Stock update WebSocket message."""
    type: str = "stock_update"
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "stock_update",
                "data": {
                    "product_id": 1,
                    "product_name": "Widget A",
                    "old_stock": 10,
                    "new_stock": 9,
                    "channel": "store"
                },
                "timestamp": "2024-01-01T12:00:00"
            }
        }
