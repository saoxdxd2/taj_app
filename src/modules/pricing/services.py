"""Business service for the pricing engine."""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import or_

from src.modules.pricing.models import PricingPolicy
from src.modules.sales.models import SaleChannel
from src.modules.inventory.models import Product
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.modules.audit.services import AuditService
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

TWO_DP = Decimal("0.01")
HUNDRED = Decimal("100")
# A discount above 100% would imply a negative price.
MAX_DISCOUNT_PERCENT = Decimal("100.00")


def _as_utc(value: datetime) -> datetime:
    """
    Normalizes a datetime for comparison.

    The columns are timezone-naive DateTime while callers may pass either
    naive or aware datetimes. Comparing the two raises in SQLAlchemy, so
    everything is normalized to naive UTC.
    """
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _quantize_money(value: Decimal) -> Decimal:
    """Rounds to 2 decimal places using the accountant's rounding rule."""
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _base_price_for_channel(product: Product, channel: SaleChannel) -> Decimal:
    """
    Returns the product's list price for a channel.

    The website has its own price column (migration c9e5f3b7d2a1); store
    and mobile app share the pinned/effective in-store price.
    """
    if channel == SaleChannel.WEBSITE:
        price = product.sale_price_website
        # A product priced for the store but not yet published on the website
        # falls back to the base ERP price rather than selling at zero.
        if price and price > 0:
            return price
    return product.effective_price


class PricingService:
    """
    Business service resolving the price a customer actually pays.
    """

    @staticmethod
    @transactional
    def get_effective_price(context: RequestContext, session, product_id: int,
                            quantity: int = 1,
                            customer_id: Optional[int] = None,
                            channel: SaleChannel = SaleChannel.STORE,
                            as_of: Optional[datetime] = None) -> Decimal:
        """
        Returns the unit price for a product, after applying the best
        applicable pricing policy.

        With no matching policy the channel's base price is returned.
        The result always has at most 2 decimal places.
        """
        PermissionManager.verify_permission(context, "Pricing.Policies.View")

        if quantity <= 0:
            raise ValueError("Quantity must be positive to resolve a price.")

        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        base_price = _base_price_for_channel(product, channel)
        as_of = _as_utc(as_of or datetime.now(timezone.utc))

        policies = PricingService.get_applicable_policies(
            session=session, product_id=product_id, quantity=quantity,
            customer_id=customer_id, channel=channel, as_of=as_of,
        )

        if not policies:
            return _quantize_money(base_price)

        best = policies[0]
        discounted = base_price * (HUNDRED - best.discount_percent) / HUNDRED
        return _quantize_money(discounted)

    @staticmethod
    def get_applicable_policies(session, product_id: int, quantity: int,
                                customer_id: Optional[int] = None,
                                channel: SaleChannel = SaleChannel.STORE,
                                as_of: Optional[datetime] = None) -> List[PricingPolicy]:
        """
        Returns the policies that apply right now, best candidate first.

        Ordering encodes the documented resolution rules:
        customer-specific before global, then priority descending,
        then the largest discount.
        """
        as_of = _as_utc(as_of or datetime.now(timezone.utc))

        # A global policy (customer_id NULL) also applies to a customer; when
        # no customer is known only global policies can apply.
        scope_filter = (
            or_(
                PricingPolicy.customer_id.is_(None),
                PricingPolicy.customer_id == customer_id,
            )
            if customer_id is not None
            else PricingPolicy.customer_id.is_(None)
        )

        policies = (
            session.query(PricingPolicy)
            .filter(
                PricingPolicy.product_id == product_id,
                PricingPolicy.min_quantity <= quantity,
                PricingPolicy.channel == channel,
                PricingPolicy.valid_from <= as_of,
                or_(
                    PricingPolicy.valid_until.is_(None),
                    PricingPolicy.valid_until >= as_of,
                ),
                scope_filter,
            )
            .all()
        )

        # Sorted in Python: SQLAlchemy cannot express "NULLs first" ordering
        # portably across SQLite and PostgreSQL, and the list is tiny.
        return sorted(
            policies,
            key=lambda p: (
                0 if p.customer_id is not None else 1,  # specific beats global
                -p.priority,                          # higher priority wins
                -p.discount_percent,                  # bigger discount wins
            ),
        )

    @staticmethod
    @transactional
    def create_policy(context: RequestContext, session, product_id: int,
                      discount_percent: Decimal,
                      min_quantity: int = 1,
                      customer_id: Optional[int] = None,
                      channel: SaleChannel = SaleChannel.STORE,
                      valid_from: Optional[datetime] = None,
                      valid_until: Optional[datetime] = None,
                      priority: int = 0,
                      label: Optional[str] = None) -> PricingPolicy:
        """
        Creates a discount policy for a product.
        customer_id=None creates a global policy.
        """
        PermissionManager.verify_permission(context, "Pricing.Policies.Create")

        if min_quantity <= 0:
            raise ValueError("Minimum quantity must be positive.")
        if discount_percent < 0 or discount_percent > MAX_DISCOUNT_PERCENT:
            raise ValueError("Discount percent must be between 0 and 100.")

        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        valid_from = _as_utc(valid_from or datetime.now(timezone.utc))
        valid_until = _as_utc(valid_until) if valid_until else None
        if valid_until is not None and valid_until < valid_from:
            raise ValueError("valid_until cannot be before valid_from.")

        policy = PricingPolicy(
            product_id=product_id,
            customer_id=customer_id,
            min_quantity=min_quantity,
            discount_percent=discount_percent,
            channel=channel,
            valid_from=valid_from,
            valid_until=valid_until,
            priority=priority,
            label=label,
        )
        session.add(policy)
        session.flush()

        AuditService.record_event(
            session=session,
            action="CREATE_PRICING_POLICY",
            entity_name="PricingPolicy",
            entity_id=str(policy.id),
            after_values={
                "product_id": product_id,
                "customer_id": customer_id,
                "min_quantity": min_quantity,
                "discount_percent": discount_percent,
                "channel": channel.value,
            },
            user_id=context.user_id,
        )
        logger.info(f"Created pricing policy {policy.id} by {context.username}.")
        return policy

    @staticmethod
    @transactional
    def list_policies_for_product(context: RequestContext, session,
                                  product_id: int) -> List[PricingPolicy]:
        """Returns every policy attached to a product, newest first."""
        PermissionManager.verify_permission(context, "Pricing.Policies.View")
        return (
            session.query(PricingPolicy)
            .filter(PricingPolicy.product_id == product_id)
            .order_by(PricingPolicy.id.desc())
            .all()
        )

    @staticmethod
    @transactional
    def delete_policy(context: RequestContext, session, policy_id: int) -> bool:
        """
        Deletes a policy.

        Policies are configuration rather than financial history, so they
        may be removed. Invoices already validated keep the price they were
        sold at, because that price is captured on the invoice line.
        """
        PermissionManager.verify_permission(context, "Pricing.Policies.Delete")

        policy = session.query(PricingPolicy).filter(PricingPolicy.id == policy_id).first()
        if not policy:
            raise ValueError(f"Pricing policy ID {policy_id} not found.")

        before = {
            "product_id": policy.product_id,
            "discount_percent": policy.discount_percent,
        }
        session.delete(policy)
        session.flush()

        AuditService.record_event(
            session=session,
            action="DELETE_PRICING_POLICY",
            entity_name="PricingPolicy",
            entity_id=str(policy_id),
            before_values=before,
            user_id=context.user_id,
        )
        logger.info(f"Deleted pricing policy {policy_id} by {context.username}.")
        return True

