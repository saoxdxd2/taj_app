import logging
from decimal import Decimal
from typing import Optional, List
from src.modules.crm.models import Customer, Address
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
    def get_all_customers(context: RequestContext, session, limit: int = 100, offset: int = 0):
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
    def get_customer_by_id(context: RequestContext, customer_id: int, session=None):
        """
        Retrieves a single customer by ID.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")
        return session.query(Customer).filter(Customer.id == customer_id).first()

    @staticmethod
    @transactional
    def update_customer(context: RequestContext, session, customer_id: int, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Optional[Customer]:
        """
        Updates an existing customer.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Update")
        
        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None
            
        if not company_name:
            raise ValueError("Company name is required.")
            
        customer.company_name = company_name
        customer.contact_name = contact_name
        customer.email = email
        customer.phone = phone
        customer.ice_number = ice_number
        
        logger.info(f"Updated customer: {company_name} by {context.username}")
        return customer

    @staticmethod
    @transactional
    def create_customer(context: RequestContext, session, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Customer:
        """
        Creates a new customer.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.Create")
        if not company_name:
            raise ValueError("Company name is required to create a customer.")
            
        customer = Customer(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            ice_number=ice_number
        )
        session.add(customer)
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
