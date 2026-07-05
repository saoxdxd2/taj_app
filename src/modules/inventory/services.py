import logging
from decimal import Decimal
from typing import Optional
from src.modules.inventory.models import Product, ProductState, ProductType

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Business service handling Inventory logic.
    """

    @staticmethod
    def create_product(session, name: str, sku: str, 
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
        logger.info(f"Created new draft product: {sku} - {name}")
        return product

    @staticmethod
    def activate_product(session, product_id: int) -> bool:
        """
        Transitions a product from Draft to Active.
        """
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return False
            
        if product.state != ProductState.DRAFT:
            logger.warning(f"Product {product.sku} is not in Draft state.")
            return False
            
        product.state = ProductState.ACTIVE
        logger.info(f"Activated product: {product.sku}")
        return True

    @staticmethod
    def archive_product(session, product_id: int) -> bool:
        """
        Transitions a product to Archived.
        Enforces the rule that products are never hard-deleted.
        """
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            return False
            
        product.state = ProductState.ARCHIVED
        logger.info(f"Archived product: {product.sku}")
        return True
