import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from src.modules.sales.models import (
    Invoice, InvoiceItem, InvoiceState, Quotation, QuotationState,
    Payment, PaymentMethod, CustomerDeposit, DepositState,
    SalesReturn, ReturnItem, ReturnType, ReturnState,
)
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional
from src.dto.sales_dto import InvoiceItemCreateDTO
from pydantic import ValidationError

logger = logging.getLogger(__name__)

def _legacy_invoice_item_error(exc: ValidationError) -> ValueError:
    """
    Translates a DTO ValidationError into the ValueError messages this
    service has always raised, so existing callers, the UI and the test
    suite keep their documented behaviour after DTO validation was added.
    """
    fields = {str(error["loc"][0]) for error in exc.errors()}

    if {"quantity", "unit_price", "vat_rate"} & fields:
        return ValueError("Quantity must be positive, prices and VAT cannot be negative.")
    if "unit_cost" in fields:
        return ValueError("Unit cost cannot be negative.")
    if "warranty_months" in fields:
        return ValueError("Warranty months cannot be negative.")
    if "description_override" in fields:
        return ValueError("Description override is too long (max 255 characters).")
    # Anything else (e.g. a bad precision) is a genuine new constraint.
    return ValueError(str(exc))

class SalesService:
    """
    Business service handling Sales logic (Invoices and Quotations).
    """

    @staticmethod
    @transactional
    def get_all_invoices(context: RequestContext, session, limit: int = 100, offset: int = 0) -> List[Invoice]:
        """
        Retrieves invoices with pagination.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        from sqlalchemy.orm import joinedload
        return (
            session.query(Invoice)
            .options(joinedload(Invoice.customer))
            .order_by(Invoice.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    @transactional
    def count_all_invoices(context: RequestContext, session) -> int:
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        return session.query(Invoice).count()

    @staticmethod
    @transactional
    def get_invoice_with_items(context: RequestContext, invoice_id: int, session=None) -> Optional[Invoice]:
        """
        Retrieves a single invoice by ID, eagerly loading its items.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        from sqlalchemy.orm import joinedload
        return (
            session.query(Invoice)
            .options(
                joinedload(Invoice.customer),
                joinedload(Invoice.items).joinedload(InvoiceItem.product),
            )
            .filter(Invoice.id == invoice_id)
            .first()
        )

    @staticmethod
    def generate_invoice_number(context: RequestContext, session) -> str:
        """
        Sequential invoice number per year: N°01-26, N°02-26, ...
        Scans the numbers already used for the current year and returns
        the next free sequence. Zero-padded to 2 digits (rolls to 3+ past 99).
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Create")
        now = datetime.now(timezone.utc)
        yy = f"{now.year % 100:02d}"
        suffix = f"-{yy}"
        rows = session.query(Invoice.invoice_number).filter(
            Invoice.invoice_number.like(f"N°%{suffix}")
        ).all()
        max_seq = 0
        for (number,) in rows:
            middle = number[2:-len(suffix)]  # strip 'N°' prefix and '-YY' suffix
            if middle.isdigit():
                max_seq = max(max_seq, int(middle))
        return f"N°{max_seq + 1:02d}-{yy}"

    @staticmethod
    @transactional
    def create_invoice_draft(context: RequestContext, session, customer_id: Optional[int],
                             invoice_number: Optional[str] = None) -> Invoice:
        """
        Creates a new invoice in Draft state.
        If no number is given, one is generated automatically (N°XX-YY).
        customer_id=None means an anonymous cash sale — it is booked on the
        shared 'Client de passage (Walk-in)' customer.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Create")
        if invoice_number is None:
            invoice_number = SalesService.generate_invoice_number(context, session=session)

        if customer_id is None:
            from src.modules.crm.services import CRMService
            customer_id = CRMService.get_or_create_walk_in_customer(
                context=context, session=session
            ).id

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            state=InvoiceState.DRAFT,
            total_amount=Decimal("0.00")
        )
        session.add(invoice)
        session.flush()  # Flush to get ID
        logger.info(f"Created new draft invoice: {invoice_number} by {context.username}")
        return invoice

    @staticmethod
    @transactional
    def add_item_to_invoice(context: RequestContext, session, invoice_id: Optional[int] = None,
                            product_id: Optional[int] = None, 
                            quantity: Optional[int] = None, unit_price: Optional[Decimal] = None,
                            vat_rate: Optional[Decimal] = None,
                            unit_cost: Decimal = Decimal("0.00"),
                            description_override: Optional[str] = None,
                            warranty_months: int = 12,
                            dto: Optional["InvoiceItemCreateDTO"] = None) -> InvoiceItem:
        """
        Adds an item to a Draft invoice and updates the total amount.
        `unit_cost` captures the REAL cost at sale time for exact margin analysis.
        `warranty_months` defaults to 12 (1 year); motors may use up to 120.

        Supply either a validated InvoiceItemCreateDTO via `dto` (boundary
        validation before any database access) or the primitive arguments,
        which are validated into a DTO here so both paths are identical.
        Existing positional/keyword callers are unaffected.
        """
        PermissionManager.verify_permission(context, "Sales.Invoices.Update")

        if dto is not None:
            line = dto
        else:
            missing = [
                name for name, value in (
                    ("invoice_id", invoice_id), ("product_id", product_id),
                    ("quantity", quantity), ("unit_price", unit_price),
                    ("vat_rate", vat_rate),
                ) if value is None
            ]
            if missing:
                raise ValueError(
                    "Missing required argument(s): " + ", ".join(missing)
                    + ". Provide either these arguments or a dto."
                )
            # `missing` being empty guarantees these are not None; the
            # asserts make that guarantee visible to the type checker.
            assert invoice_id is not None
            assert product_id is not None
            assert quantity is not None
            assert unit_price is not None
            assert vat_rate is not None
            # Validate the primitive arguments through the DTO, but translate
            # failures into the ValueError messages this service has always
            # raised, so existing callers and tests keep their behaviour.
            try:
                line = InvoiceItemCreateDTO(
                    invoice_id=invoice_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    unit_cost=unit_cost,
                    description_override=description_override,
                    warranty_months=warranty_months,
                )
            except ValidationError as exc:
                raise _legacy_invoice_item_error(exc) from exc

        # Adopt the validated values before any query runs, so the DTO-only
        # path does not fall through to the (absent) primitive arguments.
        invoice_id = line.invoice_id
        product_id = line.product_id
        quantity = line.quantity
        unit_price = line.unit_price
        vat_rate = line.vat_rate
        unit_cost = line.unit_cost
        description_override = line.description_override
        warranty_months = line.warranty_months

        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
            
        if invoice.state != InvoiceState.DRAFT:
            raise ValueError("Forbidden: Cannot modify an invoice after it has left Draft state.")

        item = InvoiceItem(
            invoice_id=invoice_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            vat_rate=vat_rate,
            unit_cost=unit_cost,
            description_override=description_override,
            warranty_months=warranty_months,
        )
        session.add(item)
        # SessionLocal disables autoflush, so flush explicitly before any
        # caller re-reads the invoice/items or needs the generated id.
        session.flush()
        
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
        #    Also stamp each item's warranty end date from the validation moment.
        validated_at = datetime.now(timezone.utc)
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
            if item.warranty_months > 0:
                item.warranty_end_date = validated_at + timedelta(days=30 * item.warranty_months)
            
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

    # ------------------------------------------------------------------
    # Payments (cash / check / virement)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def get_invoice_balance(context: RequestContext, invoice_id: int, session=None) -> Decimal:
        """Amount still owed on an invoice: total (VAT incl.) minus registered payments."""
        PermissionManager.verify_permission(context, "Sales.Invoices.View")
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
        paid = session.query(Payment).filter(Payment.invoice_id == invoice_id).all()
        return invoice.total_amount - sum((p.amount for p in paid), Decimal("0.00"))

    @staticmethod
    def _validate_incoming_check(session, check_id: Optional[int], amount: Decimal,
                                 customer_id: int):
        """
        Ensures a CHECK payment is backed by a real, usable incoming check.

        Without this link the payment looks settled on the invoice but the
        money never reaches the journal when the check clears, because
        FinanceService has no check to clear. The one-check/one-payment
        rule also prevents reusing the same paper for two invoices.
        """
        from src.modules.finance.models import Check, CheckDirection, CheckStatus

        if check_id is None:
            raise ValueError(
                "A check payment must reference a check registered in Finance."
            )

        check = session.query(Check).filter(Check.id == check_id).first()
        if not check:
            raise ValueError(f"Check ID {check_id} not found.")
        if check.direction != CheckDirection.INCOMING:
            raise ValueError("Only incoming customer checks can pay a sales invoice.")
        if check.customer_id != customer_id:
            raise ValueError(
                "The check does not belong to the customer on this document."
            )
        # A CLEARED check is allowed when it has not been linked yet: its
        # journal entry already exists (generic receipt), and linking it to
        # an invoice only allocates that money. No second journal entry is
        # posted for a CHECK payment.
        if check.status not in (
            CheckStatus.PENDING, CheckStatus.DEPOSITED, CheckStatus.CLEARED
        ):
            raise ValueError(
                f"Check #{check.check_number} is {check.status.value}; "
                "it cannot be used for a new payment."
            )
        if check.amount != amount:
            raise ValueError(
                f"Check #{check.check_number} is for {check.amount} DH; "
                f"the payment is {amount} DH. They must match."
            )

        from src.modules.sales.models import CustomerDeposit, Payment

        if session.query(Payment.id).filter(Payment.check_id == check.id).first():
            raise ValueError("This check is already linked to a payment.")
        if session.query(CustomerDeposit.id).filter(
            CustomerDeposit.check_id == check.id
        ).first():
            raise ValueError("This check is already linked to a customer deposit.")
        return check

    @staticmethod
    @transactional
    def register_payment(context: RequestContext, session, invoice_id: int, method: str,
                         amount: Decimal, check_id: Optional[int] = None,
                         reference: Optional[str] = None,
                         notes: Optional[str] = None) -> Payment:
        """
        Records money received against a validated invoice.
        CASH and TRANSFER hit the journal immediately; CHECK money is recorded
        when the check clears (see FinanceService.update_check_status).
        Marks the invoice PAID when payments cover the total.
        """
        PermissionManager.verify_permission(context, "Sales.Payments.Create")
        
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
        if invoice.state not in (InvoiceState.VALIDATED, InvoiceState.ISSUED):
            raise ValueError("Payments are only allowed on validated/issued invoices.")
        if amount <= 0:
            raise ValueError("Payment amount must be strictly positive.")
        
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            raise ValueError(f"Invalid payment method: {method}")
        
        balance = SalesService.get_invoice_balance(context, invoice_id, session=session)
        if amount > balance:
            raise ValueError(f"Payment {amount} exceeds remaining balance {balance}.")

        if method_enum == PaymentMethod.CHECK:
            SalesService._validate_incoming_check(
                session, check_id, amount, invoice.customer_id
            )
        elif check_id is not None:
            raise ValueError("check_id is only valid for Check payments.")

        payment = Payment(
            invoice_id=invoice_id,
            method=method_enum,
            amount=amount,
            check_id=check_id,
            reference=reference,
            notes=notes,
        )
        session.add(payment)
        # SessionLocal disables autoflush. Flush so the balance query below
        # sees this payment and the invoice can be marked Paid in production.
        session.flush()
        
        from src.modules.finance.services import FinanceService
        from src.modules.finance.models import TransactionType
        
        if method_enum in (PaymentMethod.CASH, PaymentMethod.TRANSFER):
            FinanceService.create_journal_entry(
                session=session,
                transaction_type=TransactionType.PAYMENT_RECEIVED,
                reference_id=f"INV-{invoice.invoice_number}",
                description=f"Payment ({method_enum.value}) for invoice {invoice.invoice_number}",
                amount=amount,
                user_id=int(context.user_id) if context.user_id else None,
            )
        # CHECK: journal entry deferred until the check clears.
        
        # Mark PAID when fully covered
        if SalesService.get_invoice_balance(context, invoice_id, session=session) <= 0:
            invoice.state = InvoiceState.PAID
        
        logger.info(f"Registered {method_enum.value} payment of {amount} on {invoice.invoice_number}.")
        return payment

    # ------------------------------------------------------------------
    # Customer deposits ('bons')
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def create_deposit(context: RequestContext, session, deposit_number: str, customer_id: int,
                       amount: Decimal, method: str = "Cash",
                       check_id: Optional[int] = None,
                       notes: Optional[str] = None) -> CustomerDeposit:
        """
        Records an advance payment ('bon'): customer pays now, receives goods later.
        Money hits the journal immediately (it is in the till).
        """
        PermissionManager.verify_permission(context, "Sales.Deposits.Create")
        
        if amount <= 0:
            raise ValueError("Deposit amount must be strictly positive.")
        if not deposit_number:
            raise ValueError("Deposit number is required.")
        
        try:
            method_enum = PaymentMethod(method)
        except ValueError:
            raise ValueError(f"Invalid payment method: {method}")

        if method_enum == PaymentMethod.CHECK:
            SalesService._validate_incoming_check(
                session, check_id, amount, customer_id
            )
        elif check_id is not None:
            raise ValueError("check_id is only valid for Check deposits.")

        deposit = CustomerDeposit(
            deposit_number=deposit_number,
            customer_id=customer_id,
            amount=amount,
            amount_used=Decimal("0.00"),
            state=DepositState.OPEN,
            method=method_enum,
            check_id=check_id,
            notes=notes,
        )
        session.add(deposit)
        # SessionLocal disables autoflush; callers need the generated id.
        session.flush()
        
        from src.modules.finance.services import FinanceService
        from src.modules.finance.models import TransactionType
        
        if method_enum in (PaymentMethod.CASH, PaymentMethod.TRANSFER):
            FinanceService.create_journal_entry(
                session=session,
                transaction_type=TransactionType.PAYMENT_RECEIVED,
                reference_id=deposit_number,
                description=f"Customer deposit (bon) received",
                amount=amount,
                user_id=int(context.user_id) if context.user_id else None,
            )
        
        logger.info(f"Created deposit {deposit_number} of {amount} for customer {customer_id}.")
        return deposit

    @staticmethod
    @transactional
    def apply_deposit_to_invoice(context: RequestContext, session, deposit_id: int,
                                 invoice_id: int, amount: Decimal) -> Payment:
        """
        Uses part of a customer deposit to pay a validated invoice.
        No new journal entry (money was already recorded when the deposit
        was received) — only the Payment record and deposit bookkeeping.
        """
        PermissionManager.verify_permission(context, "Sales.Deposits.Use")
        
        deposit = session.query(CustomerDeposit).filter(CustomerDeposit.id == deposit_id).first()
        if not deposit:
            raise ValueError(f"Deposit ID {deposit_id} not found.")
        if deposit.state != DepositState.OPEN:
            raise ValueError("Deposit is not open.")

        # A deposit backed by a check is only usable while that check is
        # still good. A bounced or cancelled check has no funds behind it.
        if deposit.check_id:
            from src.modules.finance.models import Check, CheckStatus

            check = session.query(Check).filter(Check.id == deposit.check_id).first()
            usable = (CheckStatus.PENDING, CheckStatus.DEPOSITED, CheckStatus.CLEARED)
            if check is None or check.status not in usable:
                raise ValueError(
                    "The check backing this deposit is no longer valid."
                )
        
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice ID {invoice_id} not found.")
        if invoice.state not in (InvoiceState.VALIDATED, InvoiceState.ISSUED):
            raise ValueError("Deposits can only be applied to validated/issued invoices.")

        # A deposit is customer money. Applying it to another customer's
        # invoice would pay that customer's debt with someone else's funds.
        if deposit.customer_id != invoice.customer_id:
            raise ValueError(
                "The deposit belongs to a different customer than the invoice."
            )
        
        if amount <= 0:
            raise ValueError("Applied amount must be strictly positive.")
        
        remaining_deposit = deposit.amount - deposit.amount_used
        if amount > remaining_deposit:
            raise ValueError(f"Amount exceeds remaining deposit ({remaining_deposit}).")
        
        balance = SalesService.get_invoice_balance(context, invoice_id, session=session)
        if amount > balance:
            raise ValueError(f"Amount exceeds invoice balance ({balance}).")
        
        deposit.amount_used += amount
        if deposit.amount_used >= deposit.amount:
            deposit.state = DepositState.SETTLED
        
        payment = Payment(
            invoice_id=invoice_id,
            method=deposit.method,
            amount=amount,
            check_id=deposit.check_id,
            reference=deposit.deposit_number,
            notes=f"Paid with deposit (bon) {deposit.deposit_number}",
        )
        session.add(payment)
        # SessionLocal disables autoflush. Flush so the balance query below
        # includes this deposit application before deciding invoice state.
        session.flush()
        
        if SalesService.get_invoice_balance(context, invoice_id, session=session) <= 0:
            invoice.state = InvoiceState.PAID
        
        logger.info(f"Applied {amount} from deposit {deposit.deposit_number} to {invoice.invoice_number}.")
        return payment

    # ------------------------------------------------------------------
    # Returns (refund / exchange) + factory repairs
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def create_return(context: RequestContext, session, return_number: str, customer_id: int,
                      return_type: str, items: List[dict],
                      invoice_id: Optional[int] = None,
                      notes: Optional[str] = None) -> SalesReturn:
        """
        Creates a return in Draft state.
        Each item dict: {product_id, quantity, unit_price, reason?, restock?, sent_to_factory?}
        If linked to an invoice, quantities are validated against what was sold.
        """
        PermissionManager.verify_permission(context, "Sales.Returns.Create")
        
        if not return_number:
            raise ValueError("Return number is required.")
        if not items:
            raise ValueError("A return needs at least one item.")
        
        try:
            type_enum = ReturnType(return_type)
        except ValueError:
            raise ValueError(f"Invalid return type: {return_type}")
        
        # Validate against the original invoice quantities
        sold_quantities: Dict[int, int] = {}
        if invoice_id is not None:
            invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice ID {invoice_id} not found.")
            if invoice.state not in (InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID):
                raise ValueError("Returns can only reference validated/issued/paid invoices.")
            if invoice.customer_id != customer_id:
                raise ValueError(
                    "The return customer does not match the invoice customer."
                )
            for inv_item in invoice.items:
                sold_quantities[inv_item.product_id] = sold_quantities.get(inv_item.product_id, 0) + inv_item.quantity

            # Draft and validated returns already consume the sold quantity.
            # Without this, the same unit could be refunded repeatedly by
            # creating several returns against one invoice.
            from sqlalchemy import func
            previous_returns = (
                session.query(ReturnItem.product_id, func.sum(ReturnItem.quantity))
                .join(SalesReturn, ReturnItem.return_id == SalesReturn.id)
                .filter(
                    SalesReturn.invoice_id == invoice_id,
                    SalesReturn.state.in_(
                        (ReturnState.DRAFT, ReturnState.VALIDATED)
                    ),
                )
                .group_by(ReturnItem.product_id)
                .all()
            )
            for product_id, returned_quantity in previous_returns:
                if product_id in sold_quantities:
                    sold_quantities[product_id] = max(
                        0, sold_quantities[product_id] - int(returned_quantity or 0)
                    )

        # Track what is left within this return too, so two lines for the
        # same product cannot exceed the returnable quantity together.
        remaining_quantities = dict(sold_quantities)

        total = Decimal("0.00")
        sales_return = SalesReturn(
            return_number=return_number,
            invoice_id=invoice_id,
            customer_id=customer_id,
            return_type=type_enum,
            state=ReturnState.DRAFT,
            total_amount=Decimal("0.00"),
            notes=notes,
        )
        session.add(sales_return)
        session.flush()
        
        for entry in items:
            try:
                product_id = entry["product_id"]
                quantity = entry["quantity"]
                unit_price = entry["unit_price"]
            except (KeyError, TypeError):
                raise ValueError(
                    "Each return item needs product_id, quantity and unit_price."
                )
            if quantity <= 0 or unit_price < 0:
                raise ValueError("Return quantity must be positive and price non-negative.")
            
            if invoice_id is not None:
                available = remaining_quantities.get(product_id, 0)
                if available < quantity:
                    raise ValueError(
                        f"Cannot return {quantity} of product {product_id}: "
                        f"only {available} sold on this invoice "
                        "(after previous returns)."
                    )
                remaining_quantities[product_id] = available - quantity
            
            item = ReturnItem(
                return_id=sales_return.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
                reason=entry.get("reason"),
                restock=entry.get("restock", True),
                sent_to_factory=entry.get("sent_to_factory", False),
            )
            session.add(item)
            total += Decimal(quantity) * unit_price
        
        sales_return.total_amount = total
        # SessionLocal disables autoflush. Flush so a caller that validates
        # this draft in the same session can see the new items.
        session.flush()
        logger.info(f"Created return draft {return_number} ({type_enum.value}) worth {total}.")
        return sales_return

    @staticmethod
    @transactional
    def validate_return(context: RequestContext, session, return_id: int) -> SalesReturn:
        """
        Validates a return: restocks returned goods (unless sent to factory),
        records the refund outflow for REFUND type, and audits the operation.
        """
        PermissionManager.verify_permission(context, "Sales.Returns.Validate")
        
        sales_return = session.query(SalesReturn).filter(SalesReturn.id == return_id).first()
        if not sales_return:
            raise ValueError(f"Return ID {return_id} not found.")
        if sales_return.state != ReturnState.DRAFT:
            raise ValueError("Return is not in Draft state.")
        if not sales_return.items:
            raise ValueError("Cannot validate a return with no items.")

        # Re-check the invoice limits at validation time. create_return()
        # already rejects over-returns, but two drafts could have been
        # created before this rule existed (or in separate transactions),
        # and both must not be validated into an over-refund.
        if sales_return.invoice_id is not None:
            invoice = session.query(Invoice).filter(
                Invoice.id == sales_return.invoice_id
            ).first()
            if not invoice:
                raise ValueError(
                    f"Invoice ID {sales_return.invoice_id} not found."
                )
            if invoice.state not in (
                InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID
            ):
                raise ValueError(
                    "Returns can only reference validated/issued/paid invoices."
                )
            if invoice.customer_id != sales_return.customer_id:
                raise ValueError(
                    "The return customer does not match the invoice customer."
                )

            sold_quantities: Dict[int, int] = {}
            for invoice_item in invoice.items:
                sold_quantities[invoice_item.product_id] = (
                    sold_quantities.get(invoice_item.product_id, 0)
                    + invoice_item.quantity
                )

            from sqlalchemy import func
            previous_returns = (
                session.query(
                    ReturnItem.product_id, func.sum(ReturnItem.quantity)
                )
                .join(SalesReturn, ReturnItem.return_id == SalesReturn.id)
                .filter(
                    SalesReturn.invoice_id == sales_return.invoice_id,
                    SalesReturn.state == ReturnState.VALIDATED,
                    SalesReturn.id != sales_return.id,
                )
                .group_by(ReturnItem.product_id)
                .all()
            )
            for product_id, returned_quantity in previous_returns:
                if product_id in sold_quantities:
                    sold_quantities[product_id] = max(
                        0,
                        sold_quantities[product_id]
                        - int(returned_quantity or 0),
                    )

            requested: Dict[int, int] = {}
            for return_item in sales_return.items:
                requested[return_item.product_id] = (
                    requested.get(return_item.product_id, 0)
                    + return_item.quantity
                )
            for product_id, quantity in requested.items():
                available = sold_quantities.get(product_id, 0)
                if quantity > available:
                    raise ValueError(
                        f"Cannot validate return {sales_return.return_number}: "
                        f"only {available} of product {product_id} remain "
                        "returnable on this invoice."
                    )

        from src.modules.inventory.services import InventoryService
        from src.modules.finance.services import FinanceService
        from src.modules.finance.models import TransactionType
        
        for item in sales_return.items:
            if item.restock and not item.sent_to_factory:
                InventoryService.adjust_stock(
                    context=context,
                    session=session,
                    product_id=item.product_id,
                    quantity_change=item.quantity,  # back into stock
                    movement_type="Return",
                    reference=f"RET-{sales_return.return_number}",
                    enforce_non_negative=False,
                )
        
        if sales_return.return_type == ReturnType.REFUND and sales_return.total_amount > 0:
            FinanceService.create_journal_entry(
                session=session,
                transaction_type=TransactionType.PAYMENT_SENT,
                reference_id=f"RET-{sales_return.return_number}",
                description=f"Refund to customer for return {sales_return.return_number}",
                amount=-sales_return.total_amount,  # outgoing money
                user_id=int(context.user_id) if context.user_id else None,
            )
        # EXCHANGE: no money moves; replacement goods leave stock via a normal invoice.
        
        sales_return.state = ReturnState.VALIDATED
        
        AuditService.record_event(
            session=session,
            action="VALIDATE_RETURN",
            entity_name="SalesReturn",
            entity_id=str(sales_return.id),
            after_values={"total_amount": float(sales_return.total_amount), "type": sales_return.return_type.value},
            user_id=context.user_id,
            correlation_id=sales_return.return_number,
        )
        
        logger.info(f"Validated return {sales_return.return_number}.")
        return sales_return
