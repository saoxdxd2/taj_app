import logging
from decimal import Decimal
from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState, Quotation, QuotationState
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class SalesService:
    """
    Business service handling Sales logic (Invoices and Quotations).
    """

    @staticmethod
    @transactional
    def get_all_invoices(context: RequestContext, session, limit: int = 100, offset: int = 0):
        """
        Retrieves invoices with pagination.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        return session.query(Invoice).order_by(Invoice.id.desc()).limit(limit).offset(offset).all()

    @staticmethod
    @transactional
    def count_all_invoices(context: RequestContext, session) -> int:
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        return session.query(Invoice).count()

    @staticmethod
    @transactional
    def get_invoice_with_items(context: RequestContext, invoice_id: int, session=None):
        """
        Retrieves a single invoice by ID, eagerly loading its items.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        from sqlalchemy.orm import joinedload
        return session.query(Invoice).options(joinedload(Invoice.items)).filter(Invoice.id == invoice_id).first()

    @staticmethod
    @transactional
    def create_invoice_draft(context: RequestContext, session, invoice_number: str, customer_id: int) -> Invoice:
        """
        Creates a new invoice in Draft state.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Create")
        if not invoice_number:
            raise ValueError("Invoice number is required.")
            
        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            state=InvoiceState.DRAFT,
            total_amount=Decimal("0.00")
        )
        session.add(invoice)
        logger.info(f"Created new draft invoice: {invoice_number} by {context.username}")
        return invoice

    @staticmethod
    @transactional
    def add_item_to_invoice(context: RequestContext, session, invoice_id: int, product_id: int, 
                            quantity: int, unit_price: Decimal, vat_rate: Decimal) -> InvoiceItem:
        """
        Adds an item to a Draft invoice and updates the total amount.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Update")
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
            
        if invoice.state != InvoiceState.DRAFT:
            raise ValueError("Forbidden: Cannot modify an invoice after it has left Draft state.")
            
        if quantity <= 0 or unit_price < 0 or vat_rate < 0:
            raise ValueError("Quantity must be positive, prices and VAT cannot be negative.")

        item = InvoiceItem(
            invoice_id=invoice_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            vat_rate=vat_rate
        )
        session.add(item)
        
        # Calculate line total including VAT
        line_total = (Decimal(quantity) * unit_price) * (Decimal("1") + (vat_rate / Decimal("100")))
        invoice.total_amount += line_total
        logger.info(f"Added item to Invoice ID {invoice_id} by {context.username}.")
        return item

    @staticmethod
    @transactional
    def validate_invoice(context: RequestContext, session, invoice_id: int) -> bool:
        """
        Transitions an invoice to Validated.
        Executes an Atomic Transaction across domains.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Validate")
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return False
            
        if invoice.state != InvoiceState.DRAFT:
            logger.warning(f"Invoice {invoice.invoice_number} is not in Draft state.")
            return False
            
        if not invoice.items:
            raise ValueError("Cannot validate an invoice with no items.")
            
        invoice.state = InvoiceState.VALIDATED
        
        from src.modules.inventory.services import InventoryService
        from src.modules.finance.services import FinanceService
        from src.modules.finance.models import TransactionType
        
        # 1. Trigger Stock Movement (decrease stock). Enforce invariant: Stock never becomes negative.
        for item in invoice.items:
            InventoryService.adjust_stock(
                context=context,
                session=session,
                product_id=item.product_id,
                quantity_change=-item.quantity, # Negative because it's a sale
                movement_type="Sale",
                reference=f"INV-{invoice.invoice_number}",
                enforce_non_negative=True
            )
            
        # 2. Trigger Financial Journal Entry
        FinanceService.create_journal_entry(
            session=session,
            transaction_type=TransactionType.SALE,
            reference_id=f"INV-{invoice.invoice_number}",
            description=f"Invoice validated for Customer ID {invoice.customer_id}",
            amount=invoice.total_amount # Incoming money
        )
        
        # 3. Trigger Audit Event
        AuditService.record_event(
            session=session,
            action="VALIDATE_INVOICE",
            entity_name="Invoice",
            entity_id=str(invoice.id),
            after_values={"total_amount": float(invoice.total_amount), "items_count": len(invoice.items)},
            user_id=context.user_id,
            correlation_id=invoice.invoice_number
        )
        
        logger.info(f"Validated invoice: {invoice.invoice_number} by {context.username}.")
        return True
