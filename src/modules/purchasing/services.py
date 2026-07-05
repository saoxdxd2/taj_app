import logging
from decimal import Decimal
from typing import List, Tuple
from src.modules.purchasing.models import Purchase, PurchaseItem, PurchaseState

logger = logging.getLogger(__name__)

class PurchasingService:
    """
    Business service handling Purchasing logic.
    """

    @staticmethod
    def create_purchase_draft(session, reference: str, supplier_id: int) -> Purchase:
        """
        Creates a new purchase order in Draft state.
        """
        if not reference:
            raise ValueError("Purchase reference is required.")
            
        purchase = Purchase(
            reference=reference,
            supplier_id=supplier_id,
            state=PurchaseState.DRAFT,
            total_amount=Decimal("0.00")
        )
        session.add(purchase)
        logger.info(f"Created new draft purchase: {reference}")
        return purchase

    @staticmethod
    def add_item_to_purchase(session, purchase_id: int, product_id: int, 
                             quantity: int, unit_cost: Decimal) -> PurchaseItem:
        """
        Adds an item to a Draft purchase and updates the total amount.
        """
        purchase = session.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            raise ValueError(f"Purchase ID {purchase_id} not found.")
            
        if purchase.state != PurchaseState.DRAFT:
            raise ValueError("Cannot add items to a purchase that is not in Draft state.")
            
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
            
        if unit_cost < 0:
            raise ValueError("Unit cost cannot be negative.")

        item = PurchaseItem(
            purchase_id=purchase_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost
        )
        session.add(item)
        
        # Update total
        purchase.total_amount += (Decimal(quantity) * unit_cost)
        
        logger.info(f"Added item (Product ID {product_id}, Qty {quantity}) to Purchase ID {purchase_id}.")
        return item

    @staticmethod
    def validate_purchase(session, purchase_id: int) -> bool:
        """
        Transitions a purchase to Validated.
        In a full implementation, this must also create a Stock Movement and Financial Journal Entry
        as dictated by 10_BUSINESS_ARCHITECTURE.md (Atomic Transaction).
        """
        purchase = session.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            return False
            
        if purchase.state != PurchaseState.DRAFT:
            logger.warning(f"Purchase {purchase.reference} is not in Draft state.")
            return False
            
        if not purchase.items:
            raise ValueError("Cannot validate a purchase with no items.")
            
        purchase.state = PurchaseState.VALIDATED
        # TODO: Trigger Stock Movement (increase stock)
        # TODO: Trigger Supplier Balance update
        # TODO: Trigger Financial Journal Entry
        # TODO: Trigger Audit Event
        
        logger.info(f"Validated purchase: {purchase.reference}")
        return True
