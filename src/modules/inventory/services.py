import logging
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from src.modules.inventory.models import (
    Product, ProductState, ProductType,
    AttributeDef, AttributeDataType, ProductAttribute, StockLevel,
)
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Business service handling Inventory logic.
    """

    @staticmethod
    @transactional
    def get_all_brands(context: RequestContext, session=None):
        PermissionManager.verify_permission(context, "Inventory.Brands.View")
        from src.modules.inventory.models import Brand
        return session.query(Brand).all()

    @staticmethod
    @transactional
    def get_all_categories(context: RequestContext, session):
        PermissionManager.verify_permission(context, "Inventory.Categories.View")
        from src.modules.inventory.models import Category
        return session.query(Category).all()

    @staticmethod
    @transactional
    def get_all_products(context: RequestContext, session, limit: int = 100, offset: int = 0):
        """
        Retrieves products with pagination.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.View")
        return session.query(Product).order_by(Product.id.desc()).limit(limit).offset(offset).all()

    @staticmethod
    @transactional
    def count_all_products(context: RequestContext, session) -> int:
        PermissionManager.verify_permission(context, "Inventory.Products.View")
        return session.query(Product).count()

    @staticmethod
    @transactional
    def get_product_by_id(context: RequestContext, product_id: int, session=None):
        """
        Retrieves a single product by ID.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.View")
        return session.query(Product).filter(Product.id == product_id).first()

    @staticmethod
    @transactional
    def update_product(context: RequestContext, session, product_id: int, name: str, sku: str, 
                       product_type: ProductType, purchase_price: Decimal, 
                       sale_price: Decimal, vat_rate: Decimal, 
                       brand_id: Optional[int], category_id: Optional[int]) -> Optional[Product]:
        """
        Updates an existing product.
        Ensures invariants like positive prices.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.Update")
        
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return None
            
        before_values = {
            "name": product.name, "sku": product.sku, "purchase_price": float(product.purchase_price),
            "sale_price": float(product.sale_price)
        }
            
        if purchase_price < 0 or sale_price < 0:
            raise ValueError("Prices cannot be negative.")
        if vat_rate < 0:
            raise ValueError("VAT rate cannot be negative.")
        if not sku:
            raise ValueError("SKU is required.")

        product.name = name
        product.sku = sku
        product.product_type = product_type
        product.purchase_price = purchase_price
        product.sale_price = sale_price
        product.vat_rate = vat_rate
        product.brand_id = brand_id
        product.category_id = category_id
        
        session.flush() # flush to generate updates before audit
        logger.info(f"Updated product: {sku} - {name} by {context.username}")
        return product

    @staticmethod
    @transactional
    def create_product(context: RequestContext, session, name: str, sku: str, 
                       product_type: ProductType = ProductType.PHYSICAL,
                       purchase_price: Decimal = Decimal("0.00"),
                       sale_price: Decimal = Decimal("0.00"),
                       vat_rate: Decimal = Decimal("20.00"),
                       brand_id: Optional[int] = None,
                       category_id: Optional[int] = None,
                       supplier_id: Optional[int] = None) -> Product:
        """
        Creates a new product in the Draft state.
        Ensures invariant: Negative Purchase Price is forbidden.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.Create")
        
        if purchase_price < 0 or sale_price < 0:
            raise ValueError("Prices cannot be negative.")
            
        if vat_rate < 0:
            raise ValueError("VAT rate cannot be negative.")

        if not sku:
            raise ValueError("SKU is required.")

        product = Product(
            name=name,
            sku=sku,
            product_type=product_type,
            state=ProductState.DRAFT,
            purchase_price=purchase_price,
            sale_price=sale_price,
            vat_rate=vat_rate,
            brand_id=brand_id,
            category_id=category_id,
            supplier_id=supplier_id
        )
        session.add(product)
        session.flush() # Flush to get ID
        logger.info(f"Created new draft product: {sku} - {name} by {context.username}")
        return product

    @staticmethod
    @transactional
    def activate_product(context: RequestContext, session, product_id: int) -> bool:
        """
        Transitions a product from Draft to Active.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.Update")
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return False
            
        if product.state != ProductState.DRAFT:
            logger.warning(f"Product {product.sku} is not in Draft state.")
            return False
            
        product.state = ProductState.ACTIVE
        logger.info(f"Activated product: {product.sku} by {context.username}")
        return True

    @staticmethod
    @transactional
    def archive_product(context: RequestContext, session, product_id: int) -> bool:
        """
        Transitions a product to Archived.
        Enforces the rule that products are never hard-deleted.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.Archive")
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return False
            
        product.state = ProductState.ARCHIVED
        logger.info(f"Archived product: {product.sku} by {context.username}")
        return True

    @staticmethod
    @transactional
    def adjust_stock(context: RequestContext, session, product_id: int, quantity_change: int, 
                     movement_type: str, reference: str, enforce_non_negative: bool = True) -> int:
        """
        Adjusts the stock level for a product.
        Records an immutable StockMovement.
        """
        PermissionManager.verify_permission(context, "Inventory.Stock.Update")
        
        if quantity_change == 0:
            return 0
            
        from src.modules.inventory.models import StockLevel, StockMovement, StockMovementType
        
        try:
            m_type = StockMovementType(movement_type)
        except ValueError:
            m_type = StockMovementType.MANUAL_ADJUSTMENT

        level = session.query(StockLevel).filter(StockLevel.product_id == product_id).first()
        if not level:
            level = StockLevel(product_id=product_id, quantity=0)
            session.add(level)
            
        new_quantity = level.quantity + quantity_change
        
        if enforce_non_negative and new_quantity < 0:
            raise ValueError(f"Insufficient stock for Product ID {product_id}. Available: {level.quantity}, Requested: {abs(quantity_change)}")
            
        level.quantity = new_quantity
        
        movement = StockMovement(
            product_id=product_id,
            movement_type=m_type,
            quantity_change=quantity_change,
            reference=reference
        )
        session.add(movement)
        logger.info(f"Adjusted stock for Product ID {product_id} by {quantity_change}. Ref: {reference} by {context.username}")
        return new_quantity

    @staticmethod
    @transactional
    def set_min_quantity(context: RequestContext, session, product_id: int, min_quantity: int) -> bool:
        """
        Sets the reorder threshold for a product (boss decides what to reorder).
        """
        PermissionManager.verify_permission(context, "Inventory.Stock.Update")
        if min_quantity < 0:
            raise ValueError("Minimum quantity cannot be negative.")
        level = session.query(StockLevel).filter(StockLevel.product_id == product_id).first()
        if not level:
            level = StockLevel(product_id=product_id, quantity=0, min_quantity=min_quantity)
            session.add(level)
        else:
            level.min_quantity = min_quantity
        logger.info(f"Min quantity for product {product_id} set to {min_quantity}.")
        return True

    @staticmethod
    @transactional
    def get_low_stock_products(context: RequestContext, session) -> List[dict]:
        """
        'What exists / what's lacking' view: products at or below their
        reorder threshold, with current quantity and shortfall.
        """
        PermissionManager.verify_permission(context, "Inventory.Stock.View")
        levels = session.query(StockLevel).filter(
            StockLevel.quantity <= StockLevel.min_quantity
        ).all()
        return [
            {
                "product_id": lvl.product_id,
                "sku": lvl.product.sku,
                "name": lvl.product.name,
                "quantity": lvl.quantity,
                "min_quantity": lvl.min_quantity,
                "shortfall": lvl.min_quantity - lvl.quantity,
            }
            for lvl in levels
        ]

    # ------------------------------------------------------------------
    # Dynamic product attributes (user-definable, website filters)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def create_attribute_def(context: RequestContext, session, key: str, label: str,
                             data_type: str = "Text", unit: Optional[str] = None) -> AttributeDef:
        """
        Defines a new product attribute (e.g. key='btu', label='BTU', NUMBER).
        Attributes are fully user-definable — nothing is hard-coded.
        """
        PermissionManager.verify_permission(context, "Inventory.Attributes.Create")
        
        if not key or not key.strip():
            raise ValueError("Attribute key is required.")
        key = key.strip().lower().replace(" ", "_")
        if not label or not label.strip():
            raise ValueError("Attribute label is required.")
        
        try:
            dt = AttributeDataType(data_type)
        except ValueError:
            raise ValueError(f"Invalid attribute data type: {data_type}")
        
        existing = session.query(AttributeDef).filter(AttributeDef.key == key).first()
        if existing:
            raise ValueError(f"Attribute '{key}' already exists.")
        
        attr_def = AttributeDef(key=key, label=label.strip(), data_type=dt, unit=unit)
        session.add(attr_def)
        session.flush()
        logger.info(f"Created attribute definition '{key}' ({dt.value}) by {context.username}.")
        return attr_def

    @staticmethod
    @transactional
    def get_all_attribute_defs(context: RequestContext, session) -> List[AttributeDef]:
        PermissionManager.verify_permission(context, "Inventory.Attributes.View")
        return session.query(AttributeDef).order_by(AttributeDef.label).all()

    @staticmethod
    @transactional
    def delete_attribute_def(context: RequestContext, session, attribute_def_id: int) -> bool:
        """
        Deletes an attribute definition and all its product values.
        Only allowed while no product uses it, to protect data integrity.
        """
        PermissionManager.verify_permission(context, "Inventory.Attributes.Delete")
        attr_def = session.query(AttributeDef).filter(AttributeDef.id == attribute_def_id).first()
        if not attr_def:
            return False
        in_use = session.query(ProductAttribute).filter(ProductAttribute.attribute_def_id == attribute_def_id).count()
        if in_use > 0:
            raise ValueError(f"Cannot delete '{attr_def.key}': {in_use} product(s) still use it. Archive instead.")
        session.delete(attr_def)
        logger.info(f"Deleted attribute definition '{attr_def.key}' by {context.username}.")
        return True

    @staticmethod
    @transactional
    def set_product_attribute(context: RequestContext, session, product_id: int,
                              attribute_def_id: int, value_text: str) -> ProductAttribute:
        """
        Assigns (or updates) an attribute value on a product.
        NUMBER attributes are validated as numeric.
        """
        PermissionManager.verify_permission(context, "Inventory.Attributes.Update")
        
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")
        attr_def = session.query(AttributeDef).filter(AttributeDef.id == attribute_def_id).first()
        if not attr_def:
            raise ValueError(f"Attribute definition ID {attribute_def_id} not found.")
        
        value_text = str(value_text).strip()
        if not value_text:
            raise ValueError("Attribute value cannot be empty.")
        if attr_def.data_type == AttributeDataType.NUMBER:
            try:
                Decimal(value_text)
            except InvalidOperation:
                raise ValueError(f"Attribute '{attr_def.label}' expects a number, got '{value_text}'.")
        
        pa = session.query(ProductAttribute).filter(
            ProductAttribute.product_id == product_id,
            ProductAttribute.attribute_def_id == attribute_def_id,
        ).first()
        if pa:
            pa.value_text = value_text
        else:
            pa = ProductAttribute(product_id=product_id, attribute_def_id=attribute_def_id, value_text=value_text)
            session.add(pa)
        
        logger.info(f"Set {attr_def.key}='{value_text}' on product {product.sku}.")
        return pa

    @staticmethod
    @transactional
    def get_product_attributes(context: RequestContext, session, product_id: int) -> List[dict]:
        PermissionManager.verify_permission(context, "Inventory.Attributes.View")
        pas = session.query(ProductAttribute).filter(ProductAttribute.product_id == product_id).all()
        return [
            {
                "key": pa.attribute_def.key,
                "label": pa.attribute_def.label,
                "value": pa.value_text,
                "unit": pa.attribute_def.unit,
            }
            for pa in pas
        ]
