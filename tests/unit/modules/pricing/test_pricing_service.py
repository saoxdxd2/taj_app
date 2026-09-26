"""
Tests for the pricing engine.

Covers the documented resolution rules: no policy returns the base price,
customer-specific policies beat global ones, volume tiers and validity
windows are honoured, and channels price independently.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from src.modules.pricing.models import PolicyScope
from src.modules.pricing.services import PricingService
from src.modules.sales.models import SaleChannel
from src.modules.inventory.services import InventoryService
from src.modules.crm.models import Customer
from src.modules.audit.models import AuditEvent
from src.core.context import RequestContext
from src.security.permissions import AccessDenied


def _make_product(session, admin_context, sku="PRD-01", price="100.00", web_price="0.00"):
    product = InventoryService.create_product(
        context=admin_context, session=session,
        name=f"Product {sku}", sku=sku,
        purchase_price=Decimal("60.00"), sale_price=Decimal(price),
    )
    # The website price column exists but create_product does not set it.
    product.sale_price_website = Decimal(web_price)
    session.flush()
    return product


def _make_customer(session, name="Client Prix SARL"):
    customer = Customer(company_name=name, ice_number="003584281000052")
    session.add(customer)
    session.flush()
    return customer


# --- No policy ----------------------------------------------------------

def test_no_policy_returns_base_price(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=1
    )
    assert price == Decimal("100.00")


def test_unknown_product_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="Product ID 9999 not found"):
        PricingService.get_effective_price(
            context=admin_context, session=session, product_id=9999
        )


def test_non_positive_quantity_is_rejected(session, admin_context):
    product = _make_product(session, admin_context)
    with pytest.raises(ValueError, match="Quantity must be positive"):
        PricingService.get_effective_price(
            context=admin_context, session=session, product_id=product.id, quantity=0
        )


# --- Global discounts ---------------------------------------------------

def test_global_discount_applies(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("10.00"),
    )
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=1
    )
    assert price == Decimal("90.00")


def test_price_is_quantized_to_two_decimals(session, admin_context):
    """33.33 less 10% rounds to 30.00, never to a 4-decimal value."""
    product = _make_product(session, admin_context, price="33.33")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("10.00"),
    )
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=3
    )
    assert price == Decimal("30.00")  # 33.33 * 0.9 = 29.997 -> 30.00
    assert price.as_tuple().exponent == -2



# --- Volume tiers -------------------------------------------------------

def test_volume_tier_requires_minimum_quantity(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("20.00"), min_quantity=10,
    )
    below = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=9
    )
    at_tier = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=10
    )
    assert below == Decimal("100.00")   # tier not reached
    assert at_tier == Decimal("80.00")  # 20% off


def test_largest_discount_wins_among_applicable_tiers(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("5.00"), min_quantity=1,
    )
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("25.00"), min_quantity=5,
    )
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id, quantity=6
    )
    assert price == Decimal("75.00")


# --- Customer-specific policies ----------------------------------------

def test_customer_specific_policy_beats_global(session, admin_context):
    """A negotiated 30% wins over the global 10%, because it is more specific."""
    product = _make_product(session, admin_context, price="100.00")
    customer = _make_customer(session)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("30.00"), customer_id=customer.id,
    )
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("10.00"),
    )
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        quantity=1, customer_id=customer.id,
    )
    assert price == Decimal("70.00")


def test_customer_specific_policy_does_not_leak_to_others(session, admin_context):
    """Another customer must still get the base price, not someone else's deal."""
    product = _make_product(session, admin_context, price="100.00")
    vip = _make_customer(session, "Client VIP")
    other = _make_customer(session, "Client Ordinaire")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("30.00"), customer_id=vip.id,
    )
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        quantity=1, customer_id=other.id,
    ) == Decimal("100.00")


def test_priority_breaks_ties_between_specific_policies(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    customer = _make_customer(session)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("10.00"), customer_id=customer.id, priority=0,
    )
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("20.00"), customer_id=customer.id, priority=10,
    )
    price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        quantity=1, customer_id=customer.id,
    )
    assert price == Decimal("80.00")



# --- Validity window ----------------------------------------------------

def test_expired_policy_is_ignored(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    now = datetime.now(timezone.utc)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("50.00"),
        valid_from=now - timedelta(days=30), valid_until=now - timedelta(days=1),
    )
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id
    ) == Decimal("100.00")


def test_policy_not_yet_started_is_ignored(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    now = datetime.now(timezone.utc)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("50.00"),
        valid_from=now + timedelta(days=1),
    )
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id
    ) == Decimal("100.00")


def test_as_of_resolves_a_future_policy(session, admin_context):
    """Simulating 'now' inside a future window activates the policy."""
    product = _make_product(session, admin_context, price="100.00")
    now = datetime.now(timezone.utc)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("50.00"), valid_from=now + timedelta(days=1),
    )
    future_price = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        as_of=now + timedelta(days=2),
    )
    assert future_price == Decimal("50.00")


# --- Channels -----------------------------------------------------------

def test_website_channel_uses_its_own_base_price(session, admin_context):
    product = _make_product(session, admin_context, price="100.00", web_price="90.00")
    store = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        channel=SaleChannel.STORE,
    )
    web = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        channel=SaleChannel.WEBSITE,
    )
    assert store == Decimal("100.00")
    assert web == Decimal("90.00")


def test_website_falls_back_to_store_price_when_not_published(session, admin_context):
    """A product not yet priced online must not sell at zero."""
    product = _make_product(session, admin_context, price="100.00", web_price="0.00")
    web = PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        channel=SaleChannel.WEBSITE,
    )
    assert web == Decimal("100.00")


def test_channel_specific_policies_are_independent(session, admin_context):
    product = _make_product(session, admin_context, price="100.00", web_price="200.00")
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("50.00"), channel=SaleChannel.WEBSITE,
    )
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        channel=SaleChannel.STORE,
    ) == Decimal("100.00")
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id,
        channel=SaleChannel.WEBSITE,
    ) == Decimal("100.00")  # 200.00 less 50%



# --- Policy management --------------------------------------------------

def test_create_policy_rejects_invalid_input(session, admin_context):
    product = _make_product(session, admin_context)
    with pytest.raises(ValueError, match="Minimum quantity must be positive"):
        PricingService.create_policy(
            context=admin_context, session=session, product_id=product.id,
            discount_percent=Decimal("10.00"), min_quantity=0,
        )
    with pytest.raises(ValueError, match="between 0 and 100"):
        PricingService.create_policy(
            context=admin_context, session=session, product_id=product.id,
            discount_percent=Decimal("150.00"),
        )


def test_create_policy_rejects_inverted_validity_window(session, admin_context):
    product = _make_product(session, admin_context)
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="valid_until cannot be before valid_from"):
        PricingService.create_policy(
            context=admin_context, session=session, product_id=product.id,
            discount_percent=Decimal("10.00"),
            valid_from=now, valid_until=now - timedelta(days=1),
        )


def test_policy_scope_property(session, admin_context):
    product = _make_product(session, admin_context)
    customer = _make_customer(session)
    global_policy = PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("5.00"),
    )
    specific = PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("5.00"), customer_id=customer.id,
    )
    assert global_policy.scope == PolicyScope.GLOBAL
    assert specific.scope == PolicyScope.CUSTOMER


def test_list_policies_for_product(session, admin_context):
    product = _make_product(session, admin_context)
    PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("5.00"),
    )
    policies = PricingService.list_policies_for_product(
        context=admin_context, session=session, product_id=product.id
    )
    assert len(policies) == 1
    assert policies[0].discount_percent == Decimal("5.00")


def test_delete_policy_restores_base_price(session, admin_context):
    product = _make_product(session, admin_context, price="100.00")
    policy = PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("10.00"),
    )
    assert PricingService.delete_policy(
        context=admin_context, session=session, policy_id=policy.id
    )
    assert PricingService.get_effective_price(
        context=admin_context, session=session, product_id=product.id
    ) == Decimal("100.00")


def test_delete_missing_policy_is_rejected(session, admin_context):
    with pytest.raises(ValueError, match="not found"):
        PricingService.delete_policy(
            context=admin_context, session=session, policy_id=9999
        )


# --- Audit & permissions ------------------------------------------------

def test_policy_changes_are_audited(session, admin_context):
    product = _make_product(session, admin_context)
    policy = PricingService.create_policy(
        context=admin_context, session=session, product_id=product.id,
        discount_percent=Decimal("15.00"),
    )
    created = session.query(AuditEvent).filter(
        AuditEvent.action == "CREATE_PRICING_POLICY"
    ).one()
    assert created.entity_name == "PricingPolicy"
    assert created.after_values["product_id"] == product.id

    PricingService.delete_policy(
        context=admin_context, session=session, policy_id=policy.id
    )
    deleted = session.query(AuditEvent).filter(
        AuditEvent.action == "DELETE_PRICING_POLICY"
    ).one()
    assert deleted.entity_id == str(policy.id)


def test_pricing_requires_permission(session, unauthorized_context):
    product = _make_product(session, RequestContext(
        user_id="1", username="admin", role="Administrator", permissions={"Everything"}
    ))
    with pytest.raises(AccessDenied):
        PricingService.get_effective_price(
            context=unauthorized_context, session=session, product_id=product.id
        )
    with pytest.raises(AccessDenied):
        PricingService.create_policy(
            context=unauthorized_context, session=session, product_id=product.id,
            discount_percent=Decimal("10.00"),
        )

