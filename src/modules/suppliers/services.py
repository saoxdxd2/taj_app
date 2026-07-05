import logging
from typing import Optional
from src.modules.suppliers.models import Supplier

logger = logging.getLogger(__name__)

class SupplierService:
    """
    Business service handling Suppliers logic.
    """

    @staticmethod
    def create_supplier(session, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Supplier:
        """
        Creates a new supplier.
        """
        if not company_name:
            raise ValueError("Company name is required to create a supplier.")
            
        supplier = Supplier(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            ice_number=ice_number
        )
        session.add(supplier)
        logger.info(f"Created new supplier: {company_name}")
        return supplier

    @staticmethod
    def archive_supplier(session, supplier_id: int) -> bool:
        """
        Archives a supplier (soft delete). Never deletes from the database.
        """
        supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            logger.warning(f"Failed to archive supplier: ID {supplier_id} not found.")
            return False
            
        supplier.is_archived = True
        logger.info(f"Archived supplier ID {supplier_id}: {supplier.company_name}")
        return True
