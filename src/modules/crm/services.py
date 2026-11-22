import logging
from decimal import Decimal
from typing import Optional, List
from src.modules.crm.models import Customer, Address
from src.modules.parties import PartyType, as_party_type, individual_full_name
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class CRMService:
    """
    Business service handling Customer Relationship Management logic.
    """

    @staticmethod
    @transactional
    def get_all_customers(context: RequestContext, session, limit: int = 100, offset: int = 0) -> List[Customer]:
        """
        Retrieves customers with pagination.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")
        return session.query(Customer).order_by(Customer.id.desc()).limit(limit).offset(offset).all()

    @staticmethod
    @transactional
    def count_all_customers(context: RequestContext, session) -> int:
        PermissionManager.verify_permission(context, "CRM.Customers.View")
        return session.query(Customer).count()

    @staticmethod
    @transactional
    def get_customer_by_id(context: RequestContext, customer_id: int, session=None) -> Optional[Customer]:
        """
        Retrieves a single customer by ID.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")
        return session.query(Customer).filter(Customer.id == customer_id).first()

    WALK_IN_NAME = "Client de passage (Walk-in)"

    @staticmethod
    def get_or_create_walk_in_customer(context: RequestContext, session) -> Customer:
        """
        Returns the shared 'walk-in' customer used for anonymous cash sales,
        creating it on first use. Keeps the Invoice.customer_id NOT NULL
        constraint intact while letting cash sales skip customer entry.
        """
        walk_in = (
            session.query(Customer)
            .filter(Customer.company_name == CRMService.WALK_IN_NAME)
            .first()
        )
        if not walk_in:
            walk_in = Customer(company_name=CRMService.WALK_IN_NAME)
            session.add(walk_in)
            session.flush()
            logger.info("Created shared walk-in customer for anonymous cash sales.")
        return walk_in

    @staticmethod
    @transactional
    def update_customer(context: RequestContext, session, customer_id: int, company_name: Optional[str] = None,
                        contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None,
                        party_type=None, first_name: Optional[str] = None,
                        last_name: Optional[str] = None) -> Optional[Customer]:
        """
        Updates an existing company or individual customer.
        An individual's full name is derived from first/last name and stored
        in company_name, so existing lists and documents keep working.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Update")
        
        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None

        kind = as_party_type(party_type if party_type is not None else customer.party_type)
        if kind == PartyType.INDIVIDUAL:
            first_name = first_name if first_name is not None else customer.first_name
            last_name = last_name if last_name is not None else customer.last_name
            if not (first_name or "").strip():
                raise ValueError("First name is required for an individual customer.")
            company_name = individual_full_name(first_name, last_name)
        elif not company_name:
            raise ValueError("Company name is required.")
            
        customer.party_type = kind
        customer.company_name = company_name
        customer.first_name = first_name if kind == PartyType.INDIVIDUAL else None
        customer.last_name = last_name if kind == PartyType.INDIVIDUAL else None
        customer.contact_name = contact_name
        customer.email = email
        customer.phone = phone
        customer.ice_number = ice_number
        
        logger.info(f"Updated customer: {company_name} by {context.username}")
        return customer

    @staticmethod
    @transactional
    def create_customer(context: RequestContext, session, company_name: Optional[str] = None,
                        contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None,
                        party_type=PartyType.ENTERPRISE,
                        first_name: Optional[str] = None,
                        last_name: Optional[str] = None) -> Customer:
        """
        Creates a company or an individual customer. An individual's full
        name is stored in company_name so every screen keeps one display name.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Create")

        kind = as_party_type(party_type)
        if kind == PartyType.INDIVIDUAL:
            if not (first_name or "").strip():
                raise ValueError("First name is required to create an individual customer.")
            company_name = individual_full_name(first_name, last_name)
        elif not company_name:
            raise ValueError("Company name is required to create a customer.")
            
        customer = Customer(
            party_type=kind,
            company_name=company_name,
            first_name=first_name if kind == PartyType.INDIVIDUAL else None,
            last_name=last_name if kind == PartyType.INDIVIDUAL else None,
            contact_name=contact_name,
            email=email,
            phone=phone,
            ice_number=ice_number
        )
        session.add(customer)
        session.flush()  # Flush to get ID and persist default values
        logger.info(f"Created new customer: {company_name} by {context.username}")
        return customer

    @staticmethod
    @transactional
    def archive_customer(context: RequestContext, session, customer_id: int) -> bool:
        """
        Archives a customer (soft delete). Never deletes from the database.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Archive")
        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            logger.warning(f"Failed to archive customer: ID {customer_id} not found.")
            return False
            
        customer.is_archived = True
        logger.info(f"Archived customer ID {customer_id}: {customer.company_name} by {context.username}")
        return True

    @staticmethod
    @transactional
    def add_address_to_customer(context: RequestContext, session, customer_id: int, street: str, city: str, 
                                postal_code: Optional[str] = None, country: str = "Morocco", 
                                is_primary: bool = False) -> Optional[Address]:
        """
        Adds an address to an existing customer.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Update")
        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            logger.warning(f"Failed to add address: Customer ID {customer_id} not found.")
            return None
            
        address = Address(
            customer_id=customer_id,
            street=street,
            city=city,
            postal_code=postal_code,
            country=country,
            is_primary=is_primary
        )
        session.add(address)
        logger.info(f"Added address to customer ID {customer_id} by {context.username}.")
        return address

    @staticmethod
    @transactional
    def get_customer_trade_stats(context: RequestContext, session, customer_id: int) -> dict:
        """
        Commercial relationship summary for one client:
        - invoices count / total invoiced (VAT incl.)
        - total paid and outstanding balance
        - last purchase date
        - available deposit ('bon') balance
        Aggregated in Python over this customer's rows only — volumes per
        client are small (hundreds), so this is faster than multi-join SQL.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")

        from src.modules.sales.models import Invoice, Payment, CustomerDeposit, DepositState

        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer ID {customer_id} not found.")

        invoices = session.query(Invoice).filter(Invoice.customer_id == customer_id).all()
        total_invoiced = sum((inv.total_amount for inv in invoices), Decimal("0.00"))
        invoice_ids = [inv.id for inv in invoices]

        total_paid = Decimal("0.00")
        if invoice_ids:
            payments = session.query(Payment).filter(Payment.invoice_id.in_(invoice_ids)).all()
            total_paid = sum((p.amount for p in payments), Decimal("0.00"))

        deposits = session.query(CustomerDeposit).filter(
            CustomerDeposit.customer_id == customer_id,
            CustomerDeposit.state == DepositState.OPEN,
        ).all()
        available_deposits = sum(
            (d.amount - d.amount_used for d in deposits), Decimal("0.00")
        )

        dated = [inv.created_at for inv in invoices if inv.created_at is not None]
        last_purchase = max(dated) if dated else None

        return {
            "customer_id": customer_id,
            "company_name": customer.company_name,
            "invoices_count": len(invoices),
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding_balance": total_invoiced - total_paid,
            "last_purchase": last_purchase,
            "available_deposits": available_deposits,
        }

    @staticmethod
    @transactional
    def get_customer_statement(context: RequestContext, session, customer_id: int,
                               date_from=None, date_to=None) -> dict:
        """
        Account statement ('relevé de compte') for one customer.
        Debit increases what the customer owes, credit decreases it; the
        running balance is what is still due at each line.

        Sources: validated/issued/paid invoices (debit), payments received
        and customer deposits ('bons') (credit). Applying a deposit to an
        invoice creates a Payment stamped with the deposit number — that is
        an allocation, not new money, so it is skipped to avoid crediting
        the same funds twice. Returns/refunds are paid when validated, so
        they do not change the outstanding balance.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")

        from src.modules.statements import as_naive_utc, statement_bounds
        from src.modules.sales.models import (
            CustomerDeposit, Invoice, InvoiceState, Payment,
        )

        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer ID {customer_id} not found.")

        start, end = statement_bounds(date_from, date_to)

        invoices = (
            session.query(Invoice)
            .filter(
                Invoice.customer_id == customer_id,
                Invoice.state.in_(
                    (InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID)
                ),
            )
            .all()
        )
        invoice_by_id = {invoice.id: invoice for invoice in invoices}

        payments = []
        if invoice_by_id:
            payments = (
                session.query(Payment)
                .filter(Payment.invoice_id.in_(invoice_by_id.keys()))
                .all()
            )

        deposits = (
            session.query(CustomerDeposit)
            .filter(CustomerDeposit.customer_id == customer_id)
            .all()
        )
        deposit_numbers = {deposit.deposit_number for deposit in deposits}

        movements = []
        for invoice in invoices:
            movements.append({
                "date": as_naive_utc(invoice.created_at),
                "order": 0,
                "id": invoice.id,
                "type": "Invoice",
                "document": invoice.invoice_number,
                "reference": "",
                "due_date": as_naive_utc(invoice.due_date),
                "debit": invoice.total_amount,
                "credit": Decimal("0.00"),
            })
        for payment in payments:
            if payment.reference and payment.reference in deposit_numbers:
                continue  # allocation of funds already credited as a deposit
            invoice = invoice_by_id[payment.invoice_id]
            movements.append({
                "date": as_naive_utc(payment.created_at),
                "order": 1,
                "id": payment.id,
                "type": "Payment",
                "document": invoice.invoice_number,
                "reference": payment.reference or payment.method.value,
                "due_date": None,
                "debit": Decimal("0.00"),
                "credit": payment.amount,
            })
        for deposit in deposits:
            movements.append({
                "date": as_naive_utc(deposit.created_at),
                "order": 2,
                "id": deposit.id,
                "type": "Deposit",
                "document": deposit.deposit_number,
                "reference": deposit.method.value,
                "due_date": None,
                "debit": Decimal("0.00"),
                "credit": deposit.amount,
            })

        movements.sort(key=lambda movement: (
            movement["date"], movement["order"], movement["id"]
        ))

        opening = Decimal("0.00")
        balance = Decimal("0.00")
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        rows = []
        for movement in movements:
            signed = movement["debit"] - movement["credit"]
            if start is not None and movement["date"] < start:
                opening += signed
                continue
            if end is not None and movement["date"] > end:
                continue
            balance += signed
            total_debit += movement["debit"]
            total_credit += movement["credit"]
            rows.append({
                "date": movement["date"],
                "type": movement["type"],
                "document": movement["document"],
                "reference": movement["reference"],
                "due_date": movement["due_date"],
                "debit": movement["debit"],
                "credit": movement["credit"],
                "balance": balance,
            })

        return {
            "kind": "customer",
            "party": {
                "id": customer.id,
                "name": customer.company_name,
                "phone": customer.phone,
                "email": customer.email,
            },
            "date_from": start,
            "date_to": end,
            "opening_balance": opening,
            "rows": rows,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": opening + total_debit - total_credit,
        }
