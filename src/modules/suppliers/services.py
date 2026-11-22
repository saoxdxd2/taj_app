import logging
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional
from src.modules.suppliers.models import Supplier
from src.modules.parties import PartyType, as_party_type, individual_full_name
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
    def get_all_suppliers(context: RequestContext, session, limit: int = 100, offset: int = 0) -> List[Supplier]:
        """
        Retrieves suppliers with pagination.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).order_by(Supplier.id.desc()).limit(limit).offset(offset).all()

    @staticmethod
    @transactional
    def count_all_suppliers(context: RequestContext, session) -> int:
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).count()

    @staticmethod
    @transactional
    def get_supplier_by_id(context: RequestContext, supplier_id: int, session=None) -> Optional[Supplier]:
        """
        Retrieves a single supplier by ID.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")
        return session.query(Supplier).filter(Supplier.id == supplier_id).first()

    @staticmethod
    @transactional
    def update_supplier(context: RequestContext, session, supplier_id: int, company_name: Optional[str] = None,
                        contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None,
                        party_type=None, first_name: Optional[str] = None,
                        last_name: Optional[str] = None) -> Optional[Supplier]:
        """
        Updates an existing company or individual supplier.
        Only updates the optional fields that are explicitly provided
        (not None), as before. An individual's full name is derived and
        stored in company_name.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.Update")
        supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            return None

        kind = as_party_type(party_type if party_type is not None else supplier.party_type)
        if kind == PartyType.INDIVIDUAL:
            first_name = first_name if first_name is not None else supplier.first_name
            last_name = last_name if last_name is not None else supplier.last_name
            if not (first_name or "").strip():
                raise ValueError("First name is required for an individual supplier.")
            company_name = individual_full_name(first_name, last_name)
        elif not company_name:
            raise ValueError("Company name is required.")

        supplier.party_type = kind
        supplier.company_name = company_name
        supplier.first_name = first_name if kind == PartyType.INDIVIDUAL else None
        supplier.last_name = last_name if kind == PartyType.INDIVIDUAL else None
        if contact_name is not None:
            supplier.contact_name = contact_name
        if email is not None:
            supplier.email = email
        if phone is not None:
            supplier.phone = phone
        if ice_number is not None:
            supplier.ice_number = ice_number
        
        logger.info(f"Updated supplier: {company_name} by {context.username}")
        return supplier

    @staticmethod
    @transactional
    def create_supplier(context: RequestContext, session, company_name: Optional[str] = None,
                        contact_name: Optional[str] = None, 
                        email: Optional[str] = None, phone: Optional[str] = None, 
                        ice_number: Optional[str] = None,
                        party_type=PartyType.ENTERPRISE,
                        first_name: Optional[str] = None,
                        last_name: Optional[str] = None) -> Supplier:
        """
        Creates a company or an individual supplier. An individual's full
        name is stored in company_name so every screen keeps one display name.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.Create")

        kind = as_party_type(party_type)
        if kind == PartyType.INDIVIDUAL:
            if not (first_name or "").strip():
                raise ValueError("First name is required to create an individual supplier.")
            company_name = individual_full_name(first_name, last_name)
        elif not company_name:
            raise ValueError("Company name is required to create a supplier.")
            
        supplier = Supplier(
            party_type=kind,
            company_name=company_name,
            first_name=first_name if kind == PartyType.INDIVIDUAL else None,
            last_name=last_name if kind == PartyType.INDIVIDUAL else None,
            contact_name=contact_name,
            email=email,
            phone=phone,
            ice_number=ice_number,
            is_archived=False
        )
        session.add(supplier)
        session.flush()  # Flush to get ID and persist default values
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
        session.flush()  # Ensure the change is persisted
        logger.info(f"Archived supplier ID {supplier_id}: {supplier.company_name} by {context.username}")
        return True

    @staticmethod
    @transactional
    def get_supplier_statement(context: RequestContext, session, supplier_id: int,
                               date_from=None, date_to=None) -> dict:
        """
        Account statement ('relevé fournisseur') for one supplier.
        Debit increases what we owe (a validated purchase); credit would
        decrease it (a payment to the supplier). Supplier payments are not
        recorded in this version, so the closing balance is the outstanding
        payable. The due date comes from the supplier's agreed payment terms.
        """
        PermissionManager.verify_permission(context, "Suppliers.Suppliers.View")

        from src.modules.statements import as_naive_utc, statement_bounds
        from src.modules.purchasing.models import Purchase, PurchaseState

        supplier = session.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not supplier:
            raise ValueError(f"Supplier ID {supplier_id} not found.")

        start, end = statement_bounds(date_from, date_to)

        purchases = (
            session.query(Purchase)
            .filter(
                Purchase.supplier_id == supplier_id,
                Purchase.state == PurchaseState.VALIDATED,
            )
            .all()
        )

        terms_days = int(supplier.payment_terms_days or 0)
        movements = []
        for purchase in purchases:
            created = as_naive_utc(purchase.created_at)
            movements.append({
                "date": created,
                "id": purchase.id,
                "type": "Purchase",
                "document": purchase.reference,
                "reference": "",
                "due_date": created + timedelta(days=terms_days) if terms_days else None,
                "debit": purchase.total_amount,
                "credit": Decimal("0.00"),
            })

        movements.sort(key=lambda movement: (movement["date"], movement["id"]))

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
            "kind": "supplier",
            "party": {
                "id": supplier.id,
                "name": supplier.company_name,
                "phone": supplier.phone,
                "email": supplier.email,
            },
            "date_from": start,
            "date_to": end,
            "opening_balance": opening,
            "rows": rows,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": opening + total_debit - total_credit,
        }
