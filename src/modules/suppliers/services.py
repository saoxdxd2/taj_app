import logging
from typing import Optional
from src.modules.suppliers.models import Supplier
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class SupplierService:
    """
    Business service handling Suppliers logic.
    """

    @staticmethod
    @transactional
    def get_all_suppliers(context: RequestContext, session):
        """
        Retrieves all suppliers.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).all()

    @staticmethod
    @transactional
    def get_supplier_by_id(context: RequestContext, supplier_id: int, session=None):
        """
        Retrieves a single supplier by ID.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).filter(Supplier.id == supplier_id).first()

    @staticmethod
    @transactional
    def update_supplier(context: RequestContext, session, supplier_id: int, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Optional[Supplier]:
        """
        Updates an existing supplier.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.Update")
        supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return None
            
        if not company_name:
            raise ValueError("Company name is required.")
            
        supplier.company_name = company_name
        supplier.contact_name = contact_name
        supplier.email = email
        supplier.phone = phone
        supplier.ice_number = ice_number
        
        logger.info(f"Updated supplier: {company_name} by {context.username}")
        return supplier

    @staticmethod
    @transactional
    def create_supplier(context: RequestContext, session, company_name: str, contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None) -> Supplier:
        """
        Creates a new supplier.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.Create")
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
        logger.info(f"Created new supplier: {company_name} by {context.username}")
        return supplier

    @staticmethod
    @transactional
    def archive_supplier(context: RequestContext, session, supplier_id: int) -> bool:
        """
        Archives a supplier (soft delete). Never deletes from the database.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.Archive")
        supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            logger.warning(f"Failed to archive supplier: ID {supplier_id} not found.")
            return False
            
        supplier.is_archived = True
        logger.info(f"Archived supplier ID {supplier_id}: {supplier.company_name} by {context.username}")
        return True
