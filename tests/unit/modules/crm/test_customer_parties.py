"""Company vs individual customers: derived names, validation, type switching."""
import pytest

from src.modules.crm.services import CRMService
from src.modules.parties import PartyType


def test_create_enterprise_customer_keeps_company_name(session, admin_context):
    customer = CRMService.create_customer(
        admin_context, session=session, company_name="Froid Atlas SARL"
    )

    assert customer.party_type == PartyType.ENTERPRISE
    assert customer.company_name == "Froid Atlas SARL"
    assert customer.first_name is None
    assert customer.last_name is None


def test_create_individual_customer_derives_the_display_name(session, admin_context):
    customer = CRMService.create_customer(
        admin_context, session=session, company_name=None,
        party_type="Individuel", first_name="Youssef", last_name="El Amrani",
        phone="+212600000000",
    )

    assert customer.party_type == PartyType.INDIVIDUAL
    assert customer.first_name == "Youssef"
    assert customer.last_name == "El Amrani"
    # Every existing screen shows company_name, so it must hold the full name.
    assert customer.company_name == "Youssef El Amrani"


def test_individual_customer_requires_a_first_name(session, admin_context):
    with pytest.raises(ValueError, match="First name"):
        CRMService.create_customer(
            admin_context, session=session, company_name=None,
            party_type="Individuel", last_name="El Amrani",
        )


def test_enterprise_customer_still_requires_a_company_name(session, admin_context):
    with pytest.raises(ValueError, match="Company name"):
        CRMService.create_customer(admin_context, session=session, company_name="")


def test_unknown_party_type_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="Entreprise or Individuel"):
        CRMService.create_customer(
            admin_context, session=session, company_name="X",
            party_type="Freelance",
        )


def test_switching_a_company_to_an_individual_updates_the_name(session, admin_context):
    customer = CRMService.create_customer(
        admin_context, session=session, company_name="Old Company SARL"
    )

    updated = CRMService.update_customer(
        admin_context, session=session, customer_id=customer.id,
        company_name=None, party_type="Individuel",
        first_name="Salma", last_name="Bennani",
    )

    assert updated.party_type == PartyType.INDIVIDUAL
    assert updated.company_name == "Salma Bennani"
    assert updated.first_name == "Salma"
    assert updated.last_name == "Bennani"


def test_switching_an_individual_to_a_company_clears_the_names(session, admin_context):
    customer = CRMService.create_customer(
        admin_context, session=session, party_type="Individuel",
        first_name="Salma", last_name="Bennani",
    )

    updated = CRMService.update_customer(
        admin_context, session=session, customer_id=customer.id,
        company_name="Nouvelle Societe SARL", party_type="Entreprise",
    )

    assert updated.party_type == PartyType.ENTERPRISE
    assert updated.company_name == "Nouvelle Societe SARL"
    assert updated.first_name is None
    assert updated.last_name is None
