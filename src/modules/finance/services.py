import logging
from decimal import Decimal
from typing import Optional
from src.modules.finance.models import FinancialJournalEntry, TransactionType, Expense, ExpenseCategory
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
