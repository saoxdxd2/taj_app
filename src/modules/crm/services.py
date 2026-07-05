import logging
from typing import Optional, List
from src.modules.crm.models import Customer, Address
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService

logger = logging.getLogger(__name__)

class CRMService:
    """
    Business service handling Customer Relationship Management logic.
    """

    @staticmethod
    def get_all_customers(context: RequestContext, session):
        """
        Retrieves all customers.
        """
        PermissionManager.verify_permission(context, "CRM.Customers.View")
        return session.query(Customer).all()

    @staticmethod
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
            
        before_values = {
            "company_name": customer.company_name, "contact_name": customer.contact_name,
            "email": customer.email, "phone": customer.phone, "ice_number": customer.ice_number
        }
            
        customer.company_name = company_name
        customer.contact_name = contact_name
        customer.email = email
        customer.phone = phone
        customer.ice_number = ice_number
        
        session.flush()
        after_values = {
            "company_name": customer.company_name, "contact_name": customer.contact_name,
            "email": customer.email, "phone": customer.phone, "ice_number": customer.ice_number
        }
        
        AuditService.record_event(
            session=session, action="UPDATE_CUSTOMER", entity_name="Customer", entity_id=str(customer.id),
            before_values=before_values, after_values=after_values, user_id=context.user_id,
            correlation_id=context.correlation_id
        )
        
        logger.info(f"Updated customer: {company_name} by {context.username}")
        return customer

    @staticmethod
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
        session.flush()
        
        AuditService.record_event(
            session=session, action="CREATE_CUSTOMER", entity_name="Customer", entity_id=str(customer.id),
            after_values={"company_name": company_name}, user_id=context.user_id,
            correlation_id=context.correlation_id
        )
        
        logger.info(f"Created new customer: {company_name} by {context.username}")
        return customer

    @staticmethod
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
        
        AuditService.record_event(
            session=session, action="ARCHIVE_CUSTOMER", entity_name="Customer", entity_id=str(customer.id),
            before_values={"is_archived": False}, after_values={"is_archived": True}, 
            user_id=context.user_id, correlation_id=context.correlation_id
        )
        
        logger.info(f"Archived customer ID {customer_id}: {customer.company_name} by {context.username}")
        return True

    @staticmethod
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
        session.flush()
        
        AuditService.record_event(
            session=session, action="ADD_ADDRESS", entity_name="Address", entity_id=str(address.id),
            after_values={"customer_id": customer_id, "city": city}, user_id=context.user_id,
            correlation_id=context.correlation_id
        )
        
        logger.info(f"Added address to customer ID {customer_id} by {context.username}.")
        return address
