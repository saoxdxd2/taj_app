import logging
from typing import Optional
from src.modules.suppliers.models import Supplier
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService

logger = logging.getLogger(__name__)

class SupplierService:
    """
    Business service handling Suppliers logic.
    """

    @staticmethod
    def get_all_suppliers(context: RequestContext, session):
        """
        Retrieves all suppliers.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).all()

    @staticmethod
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
            
        before_values = {
            "company_name": supplier.company_name, "contact_name": supplier.contact_name,
            "email": supplier.email, "phone": supplier.phone, "ice_number": supplier.ice_number
        }
            
        supplier.company_name = company_name
        supplier.contact_name = contact_name
        supplier.email = email
        supplier.phone = phone
        supplier.ice_number = ice_number
        
        session.flush()
        after_values = {
            "company_name": supplier.company_name, "contact_name": supplier.contact_name,
            "email": supplier.email, "phone": supplier.phone, "ice_number": supplier.ice_number
        }
        
        AuditService.record_event(
            session=session, action="UPDATE_SUPPLIER", entity_name="Supplier", entity_id=str(supplier.id),
            before_values=before_values, after_values=after_values, user_id=context.user_id,
            correlation_id=context.correlation_id
        )
        
        logger.info(f"Updated supplier: {company_name} by {context.username}")
        return supplier

    @staticmethod
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
        session.flush()
        
        AuditService.record_event(
            session=session, action="CREATE_SUPPLIER", entity_name="Supplier", entity_id=str(supplier.id),
            after_values={"company_name": company_name}, user_id=context.user_id,
            correlation_id=context.correlation_id
        )
        
        logger.info(f"Created new supplier: {company_name} by {context.username}")
        return supplier

    @staticmethod
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
        
        AuditService.record_event(
            session=session, action="ARCHIVE_SUPPLIER", entity_name="Supplier", entity_id=str(supplier.id),
            before_values={"is_archived": False}, after_values={"is_archived": True}, 
            user_id=context.user_id, correlation_id=context.correlation_id
        )
        
        logger.info(f"Archived supplier ID {supplier_id}: {supplier.company_name} by {context.username}")
        return True
