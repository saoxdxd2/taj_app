import logging
from typing import Optional, List
from src.modules.crm.models import Customer, Address

logger = logging.getLogger(__name__)

class CRMService:
    """
    Business service handling Customer Relationship Management logic.
    """

    @staticmethod
    def create_customer(session, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Customer:
        """
        Creates a new customer.
        """
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
        logger.info(f"Created new customer: {company_name}")
        return customer

    @staticmethod
    def archive_customer(session, customer_id: int) -> bool:
        """
        Archives a customer (soft delete). Never deletes from the database.
        """
        customer = session.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            logger.warning(f"Failed to archive customer: ID {customer_id} not found.")
            return False
            
        customer.is_archived = True
        logger.info(f"Archived customer ID {customer_id}: {customer.company_name}")
        return True

    @staticmethod
    def add_address_to_customer(session, customer_id: int, street: str, city: str, 
                                postal_code: Optional[str] = None, country: str = "Morocco", 
                                is_primary: bool = False) -> Optional[Address]:
        """
        Adds an address to an existing customer.
        """
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
        logger.info(f"Added address to customer ID {customer_id}.")
        return address
