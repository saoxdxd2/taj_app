"""Company vs individual suppliers: derived names and validation."""
import pytest

from src.modules.parties import PartyType
from src.modules.suppliers.services import SupplierService


def test_create_individual_supplier_derives_the_display_name(session, admin_context):
    supplier = SupplierService.create_supplier(
        admin_context, session=session, company_name=None,
        party_type="Individuel", first_name="Hassan", last_name="Ouazzani",
    )

    assert supplier.party_type == PartyType.INDIVIDUAL
    assert supplier.company_name == "Hassan Ouazzani"
    assert supplier.first_name == "Hassan"
    assert supplier.last_name == "Ouazzani"


def test_individual_supplier_requires_a_first_name(session, admin_context):
    with pytest.raises(ValueError, match="First name"):
        SupplierService.create_supplier(
            admin_context, session=session, company_name=None,
            party_type="Individuel", last_name="Ouazzani",
        )


def test_supplier_defaults_to_enterprise(session, admin_context):
    supplier = SupplierService.create_supplier(
        admin_context, session=session, company_name="Clim Distribution SARL"
    )

    assert supplier.party_type == PartyType.ENTERPRISE
    assert supplier.first_name is None
    assert supplier.last_name is None


def test_switching_a_supplier_to_an_individual(session, admin_context):
    supplier = SupplierService.create_supplier(
        admin_context, session=session, company_name="Old Supplier SARL"
    )

    updated = SupplierService.update_supplier(
        admin_context, session=session, supplier_id=supplier.id,
        company_name=None, party_type="Individuel",
        first_name="Hassan", last_name="Ouazzani",
    )

    assert updated.party_type == PartyType.INDIVIDUAL
    assert updated.company_name == "Hassan Ouazzani"
