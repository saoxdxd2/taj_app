import logging
from decimal import Decimal
from typing import Optional
from src.modules.inventory.models import Product, ProductState, ProductType
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
    def get_all_products(context: RequestContext, session):
        """
        Retrieves all products, including their brand and category relationships.
        """
        PermissionManager.verify_permission(context, "Inventory.Products.View")
        return session.query(Product).all()

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
