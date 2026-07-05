import logging
from decimal import Decimal
from typing import List, Tuple
from src.modules.purchasing.models import Purchase, PurchaseItem, PurchaseState
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class PurchasingService:
    """
    Business service handling Purchasing logic.
    """

    @staticmethod
    @transactional
    def get_all_purchases(context: RequestContext, session):
        """
        Retrieves all purchases.
        """
        PermissionManager.verify_permission(context, "Purchasing.Purchases.View")
        return session.query(Purchase).all()

    @staticmethod
    @transactional
    def get_purchase_with_items(context: RequestContext, purchase_id: int, session=None):
        """
        Retrieves a single purchase by ID, eagerly loading its items.
        """
        PermissionManager.verify_permission(context, "Purchasing.Purchases.View")
        from sqlalchemy.orm import joinedload
        return session.query(Purchase).options(joinedload(Purchase.items)).filter(Purchase.id == purchase_id).first()

    @staticmethod
    @transactional
    def create_purchase_draft(context: RequestContext, session, reference: str, supplier_id: int) -> Purchase:
        """
        Creates a new purchase order in Draft state.
        """
        PermissionManager.verify_permission(context, "Purchasing.Purchases.Create")
        if not reference:
            raise ValueError("Purchase reference is required.")
            
        purchase = Purchase(
            reference=reference,
            supplier_id=supplier_id,
            state=PurchaseState.DRAFT,
            total_amount=Decimal("0.00")
        )
        session.add(purchase)
        logger.info(f"Created new draft purchase: {reference} by {context.username}")
        return purchase

    @staticmethod
    @transactional
    def add_item_to_purchase(context: RequestContext, session, purchase_id: int, product_id: int, 
                             quantity: int, unit_cost: Decimal) -> PurchaseItem:
        """
        Adds an item to a Draft purchase and updates the total amount.
        """
        PermissionManager.verify_permission(context, "Purchasing.Purchases.Update")
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
        logger.info(f"Added item (Product ID {product_id}, Qty {quantity}) to Purchase ID {purchase_id} by {context.username}.")
        return item

    @staticmethod
    @transactional
    def validate_purchase(context: RequestContext, session, purchase_id: int) -> bool:
        """
        Transitions a purchase to Validated.
        Executes an Atomic Transaction across domains.
        """
        PermissionManager.verify_permission(context, "Purchasing.Purchases.Validate")
        purchase = session.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            return False
            
        if purchase.state != PurchaseState.DRAFT:
            logger.warning(f"Purchase {purchase.reference} is not in Draft state.")
            return False
            
        if not purchase.items:
            raise ValueError("Cannot validate a purchase with no items.")
            
        purchase.state = PurchaseState.VALIDATED
        
        from src.modules.inventory.services import InventoryService
        from src.modules.finance.services import FinanceService
        from src.modules.finance.models import TransactionType
        
        # 1. Trigger Stock Movement (increase stock)
        for item in purchase.items:
            InventoryService.adjust_stock(
                context=context,
                session=session,
                product_id=item.product_id,
                quantity_change=item.quantity,
                movement_type="Purchase",
                reference=f"PUR-{purchase.reference}"
            )
            
        # 2. Trigger Financial Journal Entry
        FinanceService.create_journal_entry(
            session=session,
            transaction_type=TransactionType.PURCHASE,
            reference_id=f"PUR-{purchase.reference}",
            description=f"Purchase validated from Supplier ID {purchase.supplier_id}",
            amount=-purchase.total_amount # Outgoing money or liability
        )
        
        # 3. Trigger Audit Event
        AuditService.record_event(
            session=session,
            action="VALIDATE_PURCHASE",
            entity_name="Purchase",
            entity_id=str(purchase.id),
            after_values={"total_amount": float(purchase.total_amount), "items_count": len(purchase.items)},
            user_id=context.user_id,
            correlation_id=purchase.reference
        )
        
        logger.info(f"Validated purchase: {purchase.reference} by {context.username}.")
        return True
