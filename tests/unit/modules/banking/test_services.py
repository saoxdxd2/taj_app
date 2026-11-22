"""BankingService: import, categorization, suggestions, matching, closing."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.core.context import RequestContext
from src.modules.accounting.models import AccountType, PaymentAccount
from src.modules.banking.models import (
    BankAllocation, BankCounterparty, BankStatement, BankTransaction,
    StatementStatus, TransactionCategory, TransactionStatus,
)
from src.modules.banking.parsing import ParsedStatement, ParsedTransaction
from src.modules.banking.services import BankingService, builtin_category
from src.modules.crm.models import Customer
from src.modules.purchasing.models import Purchase, PurchaseState
from src.modules.sales.models import Invoice, InvoiceState, Payment
from src.modules.suppliers.models import Supplier
from src.security.permissions import AccessDenied


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _account(session, name="CIH Bank"):
    account = PaymentAccount(name=name, account_type=AccountType.BANK)
    session.add(account)
    session.flush()
    return account


def _parsed(transactions, opening="1000.00"):
    """A balanced statement: closing is computed from the lines."""
    opening = Decimal(opening)
    debits = sum((t.debit for t in transactions if t.debit is not None), Decimal("0.00"))
    credits = sum((t.credit for t in transactions if t.credit is not None), Decimal("0.00"))
    return ParsedStatement(
        bank_profile="test",
        transactions=transactions,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        opening_balance=opening,
        closing_balance=opening + credits - debits,
    )


def _credit(day, label, amount, details=""):
    return ParsedTransaction(
        operation_date=date(2026, 5, day), label=label,
        credit=Decimal(amount), details=details,
    )


def _debit(day, label, amount, details=""):
    return ParsedTransaction(
        operation_date=date(2026, 5, day), label=label,
        debit=Decimal(amount), details=details,
    )


def _invoice(session, customer, number, total, state=InvoiceState.VALIDATED,
             created_at=datetime(2026, 5, 10, 9, 0)):
    invoice = Invoice(
        invoice_number=number, customer_id=customer.id, state=state,
        total_amount=Decimal(total), created_at=created_at, updated_at=created_at,
    )
    session.add(invoice)
    session.flush()
    return invoice


def _customer(session, name="Highlight Event SARL"):
    customer = Customer(company_name=name)
    session.add(customer)
    session.flush()
    return customer


def _purchase(session, supplier, reference, total):
    purchase = Purchase(
        reference=reference, supplier_id=supplier.id,
        state=PurchaseState.VALIDATED, total_amount=Decimal(total),
    )
    session.add(purchase)
    session.flush()
    return purchase


def _supplier(session, name="Brico Maroc"):
    supplier = Supplier(company_name=name)
    session.add(supplier)
    session.flush()
    return supplier


def _import(session, admin_context, account, parsed, file_name="releve.pdf",
            hash_value="hash-1", **kwargs):
    return BankingService.import_statement(
        context=admin_context, session=session, account_id=account.id,
        parsed=parsed, file_name=file_name, file_hash_value=hash_value, **kwargs
    )


# ----------------------------------------------------------------------
# Built-in classification (pure function)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("label,is_credit,expected", [
    ("REMISE CHEQUES 1234", True, TransactionCategory.CUSTOMER_CHEQUE_BATCH),
    ("PAIEMENT DE VOTRE CHEQUE 5544", False, TransactionCategory.CHEQUE_ISSUED),
    ("TVA SUR COMMISSION", False, TransactionCategory.TAX),
    ("PACKAGE MENSUEL", False, TransactionCategory.BANK_FEE),
    ("COMMISSION MOUVEMENT", False, TransactionCategory.BANK_FEE),
    ("VIREMENT RECU DE : CLIENT A", True, TransactionCategory.CUSTOMER_RECEIPT),
    ("VIREMENT VERS CONFRERE B", False, TransactionCategory.SUPPLIER_PAYMENT),
    ("VIREMENT VERS CLIENT C", False, TransactionCategory.SUPPLIER_PAYMENT),
    ("RETRAIT DAB", False, TransactionCategory.UNCLASSIFIED),
])
def test_builtin_category(label, is_credit, expected):
    transaction = ParsedTransaction(
        operation_date=date(2026, 5, 1), label=label,
        credit=Decimal("10.00") if is_credit else None,
        debit=None if is_credit else Decimal("10.00"),
    )
    assert builtin_category(transaction, label) == expected


# ----------------------------------------------------------------------
# Import
# ----------------------------------------------------------------------

def test_import_saves_lines_and_extracts_counterparty(session, admin_context):
    account = _account(session)
    parsed = _parsed([
        _credit(4, "VIREMENT RECU DE : HIGHLIGHT EVENT", "14800.00",
                details="NUM RIB : 011 780 0000123456"),
        _debit(5, "REMISE CHEQUES 778", "5000.00"),
        _debit(6, "COMMISSION MOUVEMENT", "50.00"),
    ])
    result = _import(session, admin_context, account, parsed)

    assert result["transactions"] == 3
    assert result["already_explained"] == 1
    assert result["is_balanced"] is True

    rows = session.query(BankTransaction).order_by(BankTransaction.line_no).all()
    receipt, batch, fee = rows
    assert receipt.category == TransactionCategory.CUSTOMER_RECEIPT
    assert receipt.status == TransactionStatus.PENDING
    assert receipt.counterparty == "HIGHLIGHT EVENT"
    assert receipt.counterparty_rib == "0117800000123456"
    assert batch.category == TransactionCategory.CUSTOMER_CHEQUE_BATCH
    # Fees are explained by the bank wording and need no user action.
    assert fee.status == TransactionStatus.IGNORED
    assert fee.category == TransactionCategory.BANK_FEE


def test_import_refuses_the_same_file_twice(session, admin_context):
    account = _account(session)
    parsed = _parsed([_credit(4, "VIREMENT RECU DE : CLIENT A", "100.00")])
    _import(session, admin_context, account, parsed, hash_value="same-hash")

    with pytest.raises(ValueError, match="already imported"):
        _import(session, admin_context, account, parsed,
                file_name="copie.pdf", hash_value="same-hash")
    assert session.query(BankStatement).count() == 1


def test_import_refuses_an_unbalanced_statement(session, admin_context):
    account = _account(session)
    parsed = _parsed([_credit(4, "VIREMENT RECU DE : CLIENT A", "100.00")])
    parsed.closing_balance = Decimal("9999.00")

    with pytest.raises(ValueError, match="does not balance"):
        _import(session, admin_context, account, parsed)
    assert session.query(BankStatement).count() == 0


def test_import_can_accept_an_unbalanced_file_when_asked(session, admin_context):
    account = _account(session)
    parsed = _parsed([_credit(4, "VIREMENT RECU DE : CLIENT A", "100.00")])
    parsed.closing_balance = Decimal("9999.00")

    result = _import(session, admin_context, account, parsed, allow_unbalanced=True)
    assert result["is_balanced"] is False
    assert session.query(BankStatement).count() == 1


def test_import_requires_manage_permission(session, unauthorized_context):
    account = _account(session)
    parsed = _parsed([_credit(4, "VIREMENT RECU DE : CLIENT A", "100.00")])

    with pytest.raises(AccessDenied):
        _import(session, unauthorized_context, account, parsed)


def test_custom_rule_overrides_the_builtin_category(session, admin_context):
    account = _account(session)
    BankingService.create_rule(
        context=admin_context, session=session, name="Highlight is internal",
        pattern="HIGHLIGHT EVENT", category=TransactionCategory.INTERNAL_TRANSFER,
    )
    parsed = _parsed([
        _credit(4, "VIREMENT RECU DE : HIGHLIGHT EVENT", "100.00"),
    ])
    _import(session, admin_context, account, parsed)

    row = session.query(BankTransaction).one()
    assert row.category == TransactionCategory.INTERNAL_TRANSFER
    assert row.status == TransactionStatus.IGNORED


def test_rib_memory_names_a_bare_credit_on_a_later_statement(session, admin_context):
    account = _account(session)
    first = _parsed([
        _credit(4, "VIREMENT RECU DE : M ABDERRAH", "500.00",
                details="NUM RIB : 011 780 0000654321"),
    ])
    _import(session, admin_context, account, first, hash_value="may")
    first_row = session.query(BankTransaction).one()
    BankingService.set_category(
        context=admin_context, session=session, transaction_id=first_row.id,
        category=TransactionCategory.CUSTOMER_RECEIPT,
        counterparty="M ABDERRAH",
    )
    memory = session.query(BankCounterparty).one()
    assert memory.rib == "0117800000654321"
    assert memory.name == "M ABDERRAH"

    second = _parsed([
        _credit(4, "VERSEMENT ESPECES", "700.00",
                details="NUM RIB : 011 780 0000654321"),
    ])
    _import(session, admin_context, account, second, file_name="juin.pdf",
            hash_value="june")
    new_row = session.query(BankTransaction).filter(
        BankTransaction.statement_id != first_row.statement_id
    ).one()
    assert new_row.counterparty == "M ABDERRAH"
    assert new_row.category == TransactionCategory.CUSTOMER_RECEIPT


# ----------------------------------------------------------------------
# Suggestions and matching invoices
# ----------------------------------------------------------------------

def test_suggestions_find_the_exact_open_invoice(session, admin_context):
    account = _account(session)
    customer = _customer(session)
    invoice = _invoice(session, customer, "FACT-01-26", "14800.00")
    parsed = _parsed([
        _credit(12, "VIREMENT RECU DE : HIGHLIGHT EVENT", "14800.00"),
    ])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    suggestions = BankingService.suggestions(
        context=admin_context, session=session, transaction_id=row.id
    )
    assert suggestions
    best = suggestions[0]
    assert best["kind"] == "document"
    assert best["invoice_id"] == invoice.id
    assert best["score"] == 100
    assert "exact outstanding amount" in best["reasons"]
    assert best["allocations"][0]["amount"] == Decimal("14800.00")


def test_matching_a_credit_registers_a_payment_and_pays_the_invoice(
        session, admin_context):
    account = _account(session)
    customer = _customer(session)
    invoice = _invoice(session, customer, "FACT-02-26", "14800.00")
    parsed = _parsed([
        _credit(12, "VIREMENT RECU DE : HIGHLIGHT EVENT", "14800.00",
                details="NUM RIB : 011 780 0000123456"),
    ])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    result = BankingService.match(
        context=admin_context, session=session, transaction_id=row.id,
        allocations=[{"invoice_id": invoice.id, "amount": Decimal("14800.00")}],
    )

    assert result["documents"] == ["FACT-02-26"]
    payment = session.query(Payment).one()
    assert payment.amount == Decimal("14800.00")
    assert payment.invoice_id == invoice.id
    assert invoice.state == InvoiceState.PAID
    assert row.status == TransactionStatus.MATCHED
    assert row.category == TransactionCategory.CUSTOMER_RECEIPT
    assert session.query(BankAllocation).one().payment_id == payment.id
    # The RIB now points at the customer for the next statements.
    memory = session.query(BankCounterparty).one()
    assert memory.customer_id == customer.id


def test_matching_refuses_a_total_that_differs_from_the_line(session, admin_context):
    account = _account(session)
    customer = _customer(session)
    invoice = _invoice(session, customer, "FACT-03-26", "14800.00")
    parsed = _parsed([_credit(12, "VIREMENT RECU DE : HIGHLIGHT EVENT", "14800.00")])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    with pytest.raises(ValueError, match="must match exactly"):
        BankingService.match(
            context=admin_context, session=session, transaction_id=row.id,
            allocations=[{"invoice_id": invoice.id, "amount": Decimal("14000.00")}],
        )
    assert session.query(Payment).count() == 0
    assert session.query(BankAllocation).count() == 0


def test_matching_refuses_an_invoice_on_an_outgoing_line(session, admin_context):
    account = _account(session)
    customer = _customer(session)
    invoice = _invoice(session, customer, "FACT-04-26", "500.00")
    parsed = _parsed([_debit(12, "VIREMENT VERS CONFRERE BRICO", "500.00")])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    with pytest.raises(ValueError, match="Money paid out"):
        BankingService.match(
            context=admin_context, session=session, transaction_id=row.id,
            allocations=[{"invoice_id": invoice.id, "amount": Decimal("500.00")}],
        )


def test_a_cheque_batch_proposes_the_invoices_that_add_up(session, admin_context):
    account = _account(session)
    customer = _customer(session, name="Client Cheques SARL")
    first = _invoice(session, customer, "FACT-10-26", "1000.00")
    second = _invoice(session, customer, "FACT-11-26", "2000.00")
    parsed = _parsed([_credit(15, "REMISE CHEQUES 991", "3000.00")])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    suggestions = BankingService.suggestions(
        context=admin_context, session=session, transaction_id=row.id
    )
    batch = suggestions[0]
    assert batch["kind"] == "batch"
    assert {a["invoice_id"] for a in batch["allocations"]} == {first.id, second.id}
    assert sum(a["amount"] for a in batch["allocations"]) == Decimal("3000.00")

    BankingService.match(
        context=admin_context, session=session, transaction_id=row.id,
        allocations=batch["allocations"],
    )
    assert first.state == InvoiceState.PAID
    assert second.state == InvoiceState.PAID
    assert session.query(Payment).count() == 2
    assert row.status == TransactionStatus.MATCHED


def test_a_debit_can_be_matched_to_a_validated_purchase(session, admin_context):
    account = _account(session)
    supplier = _supplier(session)
    purchase = _purchase(session, supplier, "ACH-77", "2500.00")
    parsed = _parsed([_debit(18, "VIREMENT VERS CONFRERE BRICO", "2500.00")])
    _import(session, admin_context, account, parsed)
    row = session.query(BankTransaction).one()

    suggestions = BankingService.suggestions(
        context=admin_context, session=session, transaction_id=row.id
    )
    assert suggestions[0]["purchase_id"] == purchase.id

    result = BankingService.match(
        context=admin_context, session=session, transaction_id=row.id,
        allocations=[{"purchase_id": purchase.id, "amount": Decimal("2500.00")}],
    )
    assert result["documents"] == ["ACH-77"]
    assert session.query(BankAllocation).one().purchase_id == purchase.id
    assert row.category == TransactionCategory.SUPPLIER_PAYMENT


# ----------------------------------------------------------------------
# Categorize, ignore, close and reopen
# ----------------------------------------------------------------------

def test_editing_a_line_is_refused_once_the_statement_is_closed(
        session, admin_context):
    account = _account(session)
    parsed = _parsed([_debit(20, "COMMISSION", "50.00")])
    statement_id = _import(session, admin_context, account, parsed)["id"]
    row = session.query(BankTransaction).one()

    BankingService.reconcile_statement(
        context=admin_context, session=session, statement_id=statement_id
    )
    statement = session.get(BankStatement, statement_id)
    assert statement.status == StatementStatus.RECONCILED

    with pytest.raises(ValueError, match="reopen"):
        BankingService.set_category(
            context=admin_context, session=session, transaction_id=row.id,
            category=TransactionCategory.BANK_FEE,
        )

    BankingService.reconcile_statement(
        context=admin_context, session=session, statement_id=statement_id,
        reconciled=False,
    )
    assert session.get(BankStatement, statement_id).status == StatementStatus.OPEN


def test_closing_requires_every_line_to_be_explained(session, admin_context):
    account = _account(session)
    parsed = _parsed([_credit(20, "VIREMENT RECU DE : CLIENT A", "300.00")])
    statement_id = _import(session, admin_context, account, parsed)["id"]
    row = session.query(BankTransaction).one()

    with pytest.raises(ValueError, match="need attention"):
        BankingService.reconcile_statement(
            context=admin_context, session=session, statement_id=statement_id
        )

    BankingService.ignore_transaction(
        context=admin_context, session=session, transaction_id=row.id
    )
    BankingService.reconcile_statement(
        context=admin_context, session=session, statement_id=statement_id
    )
    assert session.get(BankStatement, statement_id).status == StatementStatus.RECONCILED


def test_closing_refuses_a_statement_whose_math_is_wrong(session, admin_context):
    account = _account(session)
    parsed = _parsed([_debit(20, "COMMISSION", "50.00")])
    parsed.closing_balance = Decimal("1.00")
    statement_id = _import(
        session, admin_context, account, parsed, allow_unbalanced=True
    )["id"]

    with pytest.raises(ValueError, match="does not balance"):
        BankingService.reconcile_statement(
            context=admin_context, session=session, statement_id=statement_id
        )


def test_a_statement_with_matched_lines_cannot_be_deleted(session, admin_context):
    account = _account(session)
    customer = _customer(session)
    _invoice(session, customer, "FACT-20-26", "100.00")
    invoice = session.query(Invoice).one()
    parsed = _parsed([_credit(20, "VIREMENT RECU DE : HIGHLIGHT EVENT", "100.00")])
    statement_id = _import(session, admin_context, account, parsed)["id"]
    row = session.query(BankTransaction).one()
    BankingService.match(
        context=admin_context, session=session, transaction_id=row.id,
        allocations=[{"invoice_id": invoice.id, "amount": Decimal("100.00")}],
    )

    with pytest.raises(ValueError, match="matched lines"):
        BankingService.delete_statement(
            context=admin_context, session=session, statement_id=statement_id
        )


def test_accounts_are_listed_for_the_import_selector(session, admin_context):
    account = _account(session)
    rows = BankingService.list_accounts(context=admin_context, session=session)
    assert [row["id"] for row in rows] == [account.id]
    assert rows[0]["name"] == "CIH Bank"
    assert rows[0]["type"] == "Bank"


def test_summary_lists_imported_statements_with_a_real_balance(session, admin_context):
    account = _account(session)
    parsed = _parsed([
        _credit(4, "VIREMENT RECU DE : CLIENT A", "14800.00"),
        _debit(5, "COMMISSION", "50.00"),
    ], opening="1000.00")
    statement_id = _import(session, admin_context, account, parsed)["id"]

    summaries = BankingService.list_statements(
        context=admin_context, session=session, account_id=account.id
    )
    summary = summaries[0]
    assert summary["id"] == statement_id
    assert summary["total_credits"] == Decimal("14800.00")
    assert summary["total_debits"] == Decimal("50.00")
    assert summary["computed_closing"] == Decimal("15750.00")
    assert summary["is_balanced"] is True
    assert summary["pending"] == 1
    assert summary["ignored"] == 1
    assert summary["status"] == "Open"

    detail = BankingService.get_statement(
        context=admin_context, session=session, statement_id=statement_id
    )
    assert len(detail["transactions"]) == 2
    assert detail["statement"]["difference"] == Decimal("0.00")

    with pytest.raises(AccessDenied):
        BankingService.list_statements(
            context=RequestContext(
                user_id="9", username="guest", role="Guest", permissions=set(),
            ),
            session=session,
        )
