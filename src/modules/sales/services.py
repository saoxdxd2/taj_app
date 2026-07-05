import logging
from decimal import Decimal
from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState, Quotation, QuotationState

logger = logging.getLogger(__name__)

class SalesService:
    """
    Business service handling Sales logic (Invoices and Quotations).
    """

    @staticmethod
    def create_invoice_draft(session, invoice_number: str, customer_id: int) -> Invoice:
        """
        Creates a new invoice in Draft state.
        """
        if not invoice_number:
            raise ValueError("Invoice number is required.")
            
        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            state=InvoiceState.DRAFT,
            total_amount=Decimal("0.00")
        )
        session.add(invoice)
        logger.info(f"Created new draft invoice: {invoice_number}")
        return invoice

    @staticmethod
    def add_item_to_invoice(session, invoice_id: int, product_id: int, 
                            quantity: int, unit_price: Decimal, vat_rate: Decimal) -> InvoiceItem:
        """
        Adds an item to a Draft invoice and updates the total amount.
        """
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
        
        logger.info(f"Added item to Invoice ID {invoice_id}.")
        return item

    @staticmethod
    def validate_invoice(session, invoice_id: int) -> bool:
        """
        Transitions an invoice to Validated.
        In a full implementation, this must also create a Stock Movement (reduction) 
        and Financial Journal Entry as dictated by 10_BUSINESS_ARCHITECTURE.md (Atomic Transaction).
        """
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            return False
            
        if invoice.state != InvoiceState.DRAFT:
            logger.warning(f"Invoice {invoice.invoice_number} is not in Draft state.")
            return False
            
        if not invoice.items:
            raise ValueError("Cannot validate an invoice with no items.")
            
        invoice.state = InvoiceState.VALIDATED
        # TODO: Trigger Stock Movement (decrease stock). Enforce invariant: Stock never becomes negative.
        # TODO: Trigger Profit Calculation
        # TODO: Trigger Financial Journal Entry
        # TODO: Trigger Audit Event
        
        logger.info(f"Validated invoice: {invoice.invoice_number}")
        return True
