import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from src.modules.finance.models import (
    FinancialJournalEntry, TransactionType, Expense, ExpenseCategory,
    Check, CheckDirection, CheckStatus,
)
from src.core.context import RequestContext
from src.security.permissions import PermissionManager
from src.database.transaction import transactional

logger = logging.getLogger(__name__)

class FinanceService:
    """
    Business service handling Finance and Accounting logic.
    """

    @staticmethod
    @transactional
    def create_journal_entry(session, transaction_type: TransactionType, reference_id: str, 
                             description: str, amount: Decimal, user_id: Optional[int] = None) -> FinancialJournalEntry:
        """
        Creates an immutable financial journal entry.
        """
        entry = FinancialJournalEntry(
            transaction_type=transaction_type,
            reference_id=reference_id,
            description=description,
            amount=amount,
            user_id=user_id,
            is_reversed=False
        )
        session.add(entry)
        logger.info(f"Recorded Financial Journal Entry: {transaction_type.value} | {reference_id} | Amount: {amount}")
        return entry

    @staticmethod
    @transactional
    def reverse_journal_entry(session, original_entry_id: int, reversal_reference: str, user_id: Optional[int] = None) -> FinancialJournalEntry:
        """
        Reverses a journal entry by creating a counter-entry. 
        Enforces immutability: Never deletes or edits the original record.
        """
        original = session.query(FinancialJournalEntry).filter(FinancialJournalEntry.id == original_entry_id).first()
        if not original:
            raise ValueError("Original entry not found.")
            
        if original.is_reversed:
            raise ValueError("Entry is already reversed.")
            
        # Create counter entry
        counter_entry = FinancialJournalEntry(
            transaction_type=original.transaction_type,
            reference_id=reversal_reference,
            description=f"REVERSAL of {original.reference_id}",
            amount=-original.amount, # Negate the amount
            user_id=user_id,
            is_reversed=True,
            reversal_reference=original.reference_id
        )
        session.add(counter_entry)
        
        # Mark original as reversed
        original.is_reversed = True
        original.reversal_reference = reversal_reference
        
        logger.info(f"Reversed Journal Entry ID {original_entry_id} with new Entry {reversal_reference}")
        return counter_entry

    @staticmethod
    @transactional
    def record_expense(session, reference: str, description: str, amount: Decimal, 
                       category: ExpenseCategory = ExpenseCategory.OTHER, 
                       user_id: Optional[int] = None) -> Expense:
        """
        Records a business expense and automatically creates the corresponding journal entry.
        (Atomic Transaction)
        """
        if amount <= 0:
            raise ValueError("Expense amount must be strictly positive.")
            
        expense = Expense(
            reference=reference,
            category=category,
            description=description,
            amount=amount,
            is_archived=False
        )
        session.add(expense)
        
        # Expenses are outgoing money (Debit)
        FinanceService.create_journal_entry(
            session=session,
            transaction_type=TransactionType.EXPENSE,
            reference_id=reference,
            description=f"Expense: {description}",
            amount=-amount,
            user_id=user_id
        )
        
        logger.info(f"Recorded expense {reference} for amount {amount}.")
        return expense

    # ------------------------------------------------------------------
    # Check ledger (calendrier des chèques)
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def create_check(context: RequestContext, session, check_number: str, direction: str,
                     amount: Decimal, due_date: datetime, party_name: str,
                     bank: Optional[str] = None,
                     customer_id: Optional[int] = None,
                     supplier_id: Optional[int] = None,
                     notes: Optional[str] = None) -> Check:
        """
        Registers a physical check (incoming from a customer or outgoing to
        a supplier) with its due date. Starts in Pending status.
        """
        PermissionManager.verify_permission(context, "Finance.Checks.Create")
        
        if amount <= 0:
            raise ValueError("Check amount must be strictly positive.")
        if not check_number:
            raise ValueError("Check number is required.")
        if not party_name:
            raise ValueError("Party name is required.")
            
        try:
            dir_enum = CheckDirection(direction)
        except ValueError:
            raise ValueError(f"Invalid check direction: {direction}")
        
        if dir_enum == CheckDirection.INCOMING and not customer_id:
            raise ValueError("Incoming checks must be linked to a customer.")
        if dir_enum == CheckDirection.OUTGOING and not supplier_id:
            raise ValueError("Outgoing checks must be linked to a supplier.")
        
        check = Check(
            check_number=check_number,
            direction=dir_enum,
            status=CheckStatus.PENDING,
            amount=amount,
            due_date=due_date,
            bank=bank,
            party_name=party_name,
            customer_id=customer_id,
            supplier_id=supplier_id,
            notes=notes,
        )
        session.add(check)
        session.flush()
        logger.info(f"Registered {dir_enum.value} check #{check_number} for {amount} DH, due {due_date:%Y-%m-%d}.")
        return check

    @staticmethod
    @transactional
    def update_check_status(context: RequestContext, session, check_id: int, new_status: str) -> Check:
        """
        Transitions a check through its lifecycle: Pending -> Deposited ->
        Cleared / Bounced / Cancelled. Clearing an INCOMING check records
        the money as received; clearing an OUTGOING check records it as sent.
        """
        PermissionManager.verify_permission(context, "Finance.Checks.Update")
        
        check = session.query(Check).filter(Check.id == check_id).first()
        if not check:
            raise ValueError(f"Check ID {check_id} not found.")
        
        try:
            status_enum = CheckStatus(new_status)
        except ValueError:
            raise ValueError(f"Invalid check status: {new_status}")
        
        allowed = {
            CheckStatus.PENDING: {CheckStatus.DEPOSITED, CheckStatus.CLEARED, CheckStatus.CANCELLED},
            CheckStatus.DEPOSITED: {CheckStatus.CLEARED, CheckStatus.BOUNCED},
            CheckStatus.BOUNCED: {CheckStatus.DEPOSITED, CheckStatus.CANCELLED},
        }
        if status_enum != check.status and status_enum not in allowed.get(check.status, set()):
            raise ValueError(f"Cannot move check from {check.status.value} to {status_enum.value}.")
        
        check.status = status_enum
        
        # Money actually moved -> journal entry
        if status_enum == CheckStatus.CLEARED:
            FinanceService.create_journal_entry(
                session=session,
                transaction_type=TransactionType.PAYMENT_RECEIVED if check.direction == CheckDirection.INCOMING else TransactionType.PAYMENT_SENT,
                reference_id=f"CHECK-{check.check_number}",
                description=f"Check #{check.check_number} cleared ({check.party_name})",
                amount=check.amount if check.direction == CheckDirection.INCOMING else -check.amount,
                user_id=int(context.user_id) if context.user_id else None,
            )
        
        logger.info(f"Check #{check.check_number} moved to {status_enum.value} by {context.username}.")
        return check

    @staticmethod
    @transactional
    def get_checks_due_within(context: RequestContext, session, days: int = 7,
                              include_overdue: bool = True) -> List[Check]:
        """
        Returns pending checks whose due date falls within the next `days`
        days (plus any already overdue). Powers the friendly reminders.
        """
        PermissionManager.verify_permission(context, "Finance.Checks.View")
        
        now = datetime.now()
        horizon = now + timedelta(days=days)
        
        query = session.query(Check).filter(Check.status == CheckStatus.PENDING)
        if include_overdue:
            query = query.filter(Check.due_date <= horizon)
        else:
            query = query.filter(Check.due_date >= now, Check.due_date <= horizon)
        return query.order_by(Check.due_date.asc()).all()

    # ------------------------------------------------------------------
    # Analytics (cash flow, debtors, monthly profit)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_dt(value: datetime) -> datetime:
        """Make naive datetimes UTC-aware to match timezone-aware columns."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    @transactional
    def get_cash_flow(context: RequestContext, session,
                      start: Optional[datetime] = None,
                      end: Optional[datetime] = None) -> dict:
        """
        Money in / money out / net for a period, straight from the immutable
        journal (reversed entries excluded). Defaults to the current month.
        One SQL GROUP BY regardless of volume.
        """
        PermissionManager.verify_permission(context, "Finance.Reports.View")
        session.flush()  # make pending writes visible to the aggregation

        from sqlalchemy import func

        now = datetime.now(timezone.utc)
        if start is None:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = now
        if start >= end:
            raise ValueError("Period start must be before end.")
        start, end = FinanceService._normalize_dt(start), FinanceService._normalize_dt(end)

        rows = (
            session.query(
                FinancialJournalEntry.transaction_type,
                func.coalesce(func.sum(FinancialJournalEntry.amount), 0),
            )
            .filter(
                FinancialJournalEntry.is_reversed == False,  # noqa: E712
                FinancialJournalEntry.created_at >= start,
                FinancialJournalEntry.created_at < end,
            )
            .group_by(FinancialJournalEntry.transaction_type)
            .all()
        )

        breakdown = {}
        inflow = outflow = Decimal("0.00")
        for t_type, total in rows:
            amount = Decimal(str(total))
            breakdown[t_type.value] = amount
            if amount >= 0:
                inflow += amount
            else:
                outflow += abs(amount)

        return {
            "start": start,
            "end": end,
            "inflow": inflow,
            "outflow": outflow,
            "net": inflow - outflow,
            "breakdown": breakdown,
        }

    @staticmethod
    @transactional
    def get_debtors(context: RequestContext, session) -> List[dict]:
        """
        Clients who still owe money: outstanding balance per customer,
        computed with two SQL aggregations (invoiced vs paid), merged in
        Python. Only customers with a positive balance are returned.
        """
        PermissionManager.verify_permission(context, "Finance.Reports.View")
        session.flush()  # make pending writes visible to the aggregation

        from sqlalchemy import func
        from src.modules.sales.models import Invoice, Payment, InvoiceState

        states = [InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID]

        invoiced_rows = (
            session.query(
                Invoice.customer_id,
                func.coalesce(func.sum(Invoice.total_amount), 0),
            )
            .filter(Invoice.state.in_(states))
            .group_by(Invoice.customer_id)
            .all()
        )
        paid_rows = (
            session.query(
                Invoice.customer_id,
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .join(Payment, Payment.invoice_id == Invoice.id)
            .filter(Invoice.state.in_(states))
            .group_by(Invoice.customer_id)
            .all()
        )

        from src.modules.crm.models import Customer
        totals: dict = {}
        for customer_id, total in invoiced_rows:
            totals[customer_id] = {"invoiced": Decimal(str(total)), "paid": Decimal("0.00")}
        for customer_id, total in paid_rows:
            entry = totals.setdefault(customer_id, {"invoiced": Decimal("0.00"), "paid": Decimal("0.00")})
            entry["paid"] = Decimal(str(total))

        customer_ids = list(totals.keys())
        names = {}
        if customer_ids:
            for c in session.query(Customer).filter(Customer.id.in_(customer_ids)).all():
                names[c.id] = c.company_name

        debtors = []
        for customer_id, entry in totals.items():
            outstanding = entry["invoiced"] - entry["paid"]
            if outstanding > 0:
                debtors.append({
                    "customer_id": customer_id,
                    "company_name": names.get(customer_id, f"Client #{customer_id}"),
                    "total_invoiced": entry["invoiced"],
                    "total_paid": entry["paid"],
                    "outstanding": outstanding,
                })
        debtors.sort(key=lambda d: d["outstanding"], reverse=True)
        return debtors

    @staticmethod
    @transactional
    def get_monthly_profit_series(context: RequestContext, session, year: int) -> List[dict]:
        """
        Revenue / cost / gross margin per month for a given year, from the
        captured real costs. One grouped query over invoice items, bucketed
        by month in Python (portable across databases).
        """
        PermissionManager.verify_permission(context, "Finance.Reports.View")
        session.flush()  # make pending writes visible to the aggregation

        if not 2000 <= year <= 2100:
            raise ValueError(f"Invalid year: {year}")

        from sqlalchemy import func
        from src.modules.sales.models import Invoice, InvoiceItem, InvoiceState

        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

        rows = (
            session.query(
                Invoice.created_at,
                func.coalesce(func.sum(InvoiceItem.quantity * InvoiceItem.unit_price), 0),
                func.coalesce(func.sum(InvoiceItem.quantity * InvoiceItem.unit_cost), 0),
            )
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .filter(
                Invoice.state.in_([InvoiceState.VALIDATED, InvoiceState.ISSUED, InvoiceState.PAID]),
                Invoice.created_at >= start,
                Invoice.created_at < end,
            )
            .group_by(Invoice.id)
            .all()
        )

        months = [
            {"month": m, "revenue_excl_vat": Decimal("0.00"), "total_cost": Decimal("0.00"),
             "gross_margin": Decimal("0.00")}
            for m in range(1, 13)
        ]
        for created_at, revenue, cost in rows:
            if created_at is None:
                continue
            bucket = months[created_at.month - 1]
            bucket["revenue_excl_vat"] += Decimal(str(revenue))
            bucket["total_cost"] += Decimal(str(cost))

        for bucket in months:
            bucket["gross_margin"] = bucket["revenue_excl_vat"] - bucket["total_cost"]
        return months
