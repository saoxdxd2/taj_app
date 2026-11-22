"""Bank statement import, categorization and reconciliation.

The service never changes the source line: a statement is evidence. Actions
add state around it (category, counterparty, allocations) and, when an
invoice is matched, the money is recorded through the existing sales
service so the invoice really becomes paid.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import List, Optional, Sequence

from sqlalchemy import case, func

from src.core.context import RequestContext
from src.database.transaction import transactional
from src.modules.accounting.models import PaymentAccount
from src.modules.banking.models import (
    BankAllocation, BankCounterparty, BankRule, BankStatement, BankTransaction,
    MatchMethod, RuleDirection, StatementStatus, TransactionCategory,
    TransactionStatus,
)
from src.modules.banking.parsing import ParsedStatement, ParsedTransaction
from src.modules.crm.models import Customer
from src.modules.purchasing.models import Purchase, PurchaseState
from src.modules.sales.models import Invoice, InvoiceState, Payment
from src.modules.sales.services import SalesService
from src.modules.suppliers.models import Supplier
from src.security.permissions import AccessDenied, PermissionManager

EXPLAINED_CATEGORIES = {
    TransactionCategory.BANK_FEE,
    TransactionCategory.TAX,
    TransactionCategory.INTERNAL_TRANSFER,
    TransactionCategory.OTHER,
}

_LEGAL_SUFFIXES = re.compile(
    r'\b(SARL|SAS|SA|STE|SCI|SNC|EURL|SUARL)\b', re.IGNORECASE
)
_CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Amount must be a valid number.")


def _enum(enum_class, value, label: str):
    if isinstance(value, enum_class):
        return value
    try:
        return enum_class(value)
    except (ValueError, TypeError):
        try:
            return enum_class[str(value).upper()]
        except (KeyError, AttributeError):
            valid = ", ".join(item.value for item in enum_class)
            raise ValueError(f"Invalid {label}: {value!r}. Valid values: {valid}.")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper().replace("&", " ET ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _party_key(text: str) -> str:
    key = _LEGAL_SUFFIXES.sub(" ", normalize_text(text))
    return re.sub(r"\s+", " ", key).strip()


def _name_score(counterparty: Optional[str], party_name: Optional[str]) -> int:
    if not counterparty or not party_name:
        return 0
    left, right = _party_key(counterparty), _party_key(party_name)
    if not left or not right:
        return 0
    if left == right or left.replace(" ", "") == right.replace(" ", ""):
        return 35
    if len(min(left, right, key=len)) >= 4 and (left in right or right in left):
        return 27
    ratio = SequenceMatcher(None, left, right).ratio()
    if ratio >= 0.8:
        return 24
    if ratio >= 0.65:
        return 16
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if overlap >= 0.5:
            return 14
    return 0


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_counterparty(text: str) -> Optional[str]:
    text = _squash(text)
    match = re.search(
        r"VIREMENT RECU DE\s*:\s*(.+?)\s*(?:,|NUM RIB|$)", text, re.IGNORECASE
    )
    if match:
        return _clean_party(match.group(1))
    match = re.search(r"Direct vers\s+(.+)$", text, re.IGNORECASE)
    if match:
        return _clean_party(match.group(1))
    match = re.search(r"(?:Direct|ment)\s+vers\s+(.+)$", text, re.IGNORECASE)
    if match:
        return _clean_party(match.group(1))
    return None


def _clean_party(value: str) -> Optional[str]:
    value = re.sub(r"\s*(?:,|;|:)\s*$", "", _squash(value))
    value = re.sub(r"\s+(?:MOTIF|LIBELLE)$", "", value, flags=re.IGNORECASE)
    return value[:150] if value else None


def extract_rib(text: str) -> Optional[str]:
    match = re.search(r"(?:NUM\s+RIB|RIB)\s*:\s*([\d ]{15,30})", text, re.IGNORECASE)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return digits[:24] if len(digits) >= 15 else None


def extract_reference(text: str) -> Optional[str]:
    for pattern in (
        r"CHEQUE NUMERO\s+(\d{4,})",
        r"NUMERO\s+(\d{4,})",
        r"REFERENCE\s+(\d{4,})",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)[:50]
    return None


def builtin_category(transaction: ParsedTransaction, text: str) -> TransactionCategory:
    text = normalize_text(text)
    is_credit = transaction.credit is not None

    if "REMISE CHEQUES" in text:
        return TransactionCategory.CUSTOMER_CHEQUE_BATCH
    if "PAIEMENT DE VOTRE CHEQUE" in text:
        return TransactionCategory.CHEQUE_ISSUED
    if "TVA SUR" in text:
        return TransactionCategory.TAX
    if any(word in text for word in (
        "COMMISSION", "PACKAGE", "AGIOS", "PRELEVEMENT", "FRAIS",
        "BANCASSURANCE", "FPL",
    )):
        return TransactionCategory.BANK_FEE
    if "VERS CLIENT" in text and "VIREMENT" in text:
        return TransactionCategory.SUPPLIER_PAYMENT
    if "VIREMENT RECU DE" in text or "CREDIT VIREMENT" in text:
        return TransactionCategory.CUSTOMER_RECEIPT
    if "VERS CONFRERE" in text and "VIREMENT" in text:
        return TransactionCategory.SUPPLIER_PAYMENT
    if "VIREMENT RECU" in text:
        return TransactionCategory.CUSTOMER_RECEIPT
    if "VIREMENT" in text:
        return (TransactionCategory.CUSTOMER_RECEIPT if is_credit
                else TransactionCategory.SUPPLIER_PAYMENT)
    return TransactionCategory.UNCLASSIFIED


class BankingService:
    """Import statements and reconcile their lines with the sales ledger."""

    PERM_VIEW = "Accounting.Reconciliation.View"
    PERM_MANAGE = "Accounting.Reconciliation.Manage"

    @staticmethod
    def _require(context: Optional[RequestContext], permission: str) -> None:
        if context is None:
            raise AccessDenied("Authentication is required for this operation.")
        PermissionManager.verify_permission(context, permission)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def import_statement(context: RequestContext, session, account_id: int,
                         parsed: ParsedStatement, file_name: str,
                         file_hash_value: Optional[str] = None,
                         allow_unbalanced: bool = False) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)

        account = session.get(PaymentAccount, account_id)
        if account is None:
            raise ValueError("Payment account not found.")
        if not parsed.transactions:
            raise ValueError("The file contains no transaction lines.")

        if file_hash_value:
            duplicate = session.query(BankStatement).filter(
                BankStatement.file_hash == file_hash_value
            ).first()
            if duplicate:
                raise ValueError(
                    f"This file was already imported as '{duplicate.file_name}' "
                    f"on {duplicate.created_at:%d/%m/%Y}."
                )

        if not parsed.balanced and not allow_unbalanced:
            raise ValueError(
                "The statement does not balance, so it was not imported:\n- "
                + "\n- ".join(parsed.issues())
            )

        statement = BankStatement(
            account_id=account_id,
            file_name=file_name[:255],
            file_hash=file_hash_value or f"{file_name}-{_now().isoformat()}",
            bank_profile=parsed.bank_profile,
            account_number=parsed.account_number,
            period_start=parsed.period_start,
            period_end=parsed.period_end,
            opening_balance=parsed.opening_balance,
            closing_balance=parsed.closing_balance,
            declared_debit_total=parsed.declared_debit_total,
            declared_credit_total=parsed.declared_credit_total,
            imported_by=int(context.user_id) if str(context.user_id).isdigit() else None,
        )
        session.add(statement)
        session.flush()

        explained = 0
        for line_no, parsed_tx in enumerate(parsed.transactions, start=1):
            text = f"{parsed_tx.label} {parsed_tx.details}".strip()
            category, counterparty, rib, reference = BankingService._classify(
                session, account_id, parsed_tx, text
            )
            status = (TransactionStatus.IGNORED
                      if category in EXPLAINED_CATEGORIES
                      else TransactionStatus.PENDING)
            if status == TransactionStatus.IGNORED:
                explained += 1
            session.add(BankTransaction(
                statement_id=statement.id,
                line_no=line_no,
                operation_date=parsed_tx.operation_date,
                value_date=parsed_tx.value_date,
                label=parsed_tx.label[:255],
                details=parsed_tx.details or None,
                debit=parsed_tx.debit,
                credit=parsed_tx.credit,
                counterparty=counterparty,
                counterparty_rib=rib,
                reference=reference,
                category=category,
                status=status,
                match_method=MatchMethod.RULE if category != TransactionCategory.UNCLASSIFIED else None,
                match_note="Detected automatically" if status == TransactionStatus.IGNORED else None,
            ))

        session.flush()
        return {
            "id": statement.id,
            "transactions": len(parsed.transactions),
            "already_explained": explained,
            "is_balanced": parsed.balanced,
        }

    @staticmethod
    def _classify(session, account_id: int, transaction: ParsedTransaction,
                  text: str):
        counterparty = extract_counterparty(text)
        rib = extract_rib(text)
        reference = extract_reference(text)
        category = builtin_category(transaction, text)

        direction = RuleDirection.IN if transaction.credit is not None else RuleDirection.OUT
        rules = session.query(BankRule).filter(
            BankRule.is_active.is_(True)
        ).order_by(BankRule.priority, BankRule.id).all()
        for rule in rules:
            if rule.direction not in (RuleDirection.ANY, direction):
                continue
            if rule.pattern.lower() in text.lower():
                category = rule.category
                counterparty = rule.counterparty or counterparty
                break

        memory = None
        if rib:
            memory = session.query(BankCounterparty).filter(
                BankCounterparty.account_id == account_id,
                BankCounterparty.rib == rib,
            ).first()
        if memory:
            counterparty = counterparty or memory.name
            if category == TransactionCategory.UNCLASSIFIED:
                category = (TransactionCategory.CUSTOMER_RECEIPT
                            if transaction.credit is not None
                            else TransactionCategory.SUPPLIER_PAYMENT)
        return category, counterparty, rib, reference

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def list_accounts(context: RequestContext, session) -> List[dict]:
        """Accounts that can own a statement, for the import selector."""
        BankingService._require(context, BankingService.PERM_VIEW)
        accounts = session.query(PaymentAccount).order_by(PaymentAccount.name).all()
        return [{
            "id": account.id,
            "name": account.name,
            "type": account.account_type.value,
            "bank": account.bank,
            "account_number": account.account_number,
            "is_active": account.is_active,
        } for account in accounts]

    @staticmethod
    @transactional
    def list_statements(context: RequestContext, session,
                        account_id: Optional[int] = None) -> List[dict]:
        BankingService._require(context, BankingService.PERM_VIEW)

        query = session.query(BankStatement, PaymentAccount.name).join(
            PaymentAccount, PaymentAccount.id == BankStatement.account_id
        )
        if account_id is not None:
            query = query.filter(BankStatement.account_id == account_id)
        rows = query.order_by(
            BankStatement.period_end.is_(None),
            BankStatement.period_end.desc(),
            BankStatement.id.desc(),
        ).all()

        aggregates = {
            statement_id: {
                "debits": debits or Decimal("0.00"),
                "credits": credits or Decimal("0.00"),
                "pending": pending or 0,
                "matched": matched or 0,
                "ignored": ignored or 0,
            }
            for statement_id, debits, credits, pending, matched, ignored in (
                session.query(
                    BankTransaction.statement_id,
                    func.sum(BankTransaction.debit),
                    func.sum(BankTransaction.credit),
                    func.sum(case((BankTransaction.status == TransactionStatus.PENDING, 1), else_=0)),
                    func.sum(case((BankTransaction.status == TransactionStatus.MATCHED, 1), else_=0)),
                    func.sum(case((BankTransaction.status == TransactionStatus.IGNORED, 1), else_=0)),
                ).group_by(BankTransaction.statement_id).all()
            )
        }

        result = []
        for statement, account_name in rows:
            stats = aggregates.get(statement.id, {
                "debits": Decimal("0.00"), "credits": Decimal("0.00"),
                "pending": 0, "matched": 0, "ignored": 0,
            })
            result.append({
                "id": statement.id,
                "account_id": statement.account_id,
                "account_name": account_name,
                "file_name": statement.file_name,
                "bank_profile": statement.bank_profile,
                "period_start": _as_date(statement.period_start),
                "period_end": _as_date(statement.period_end),
                "opening_balance": statement.opening_balance,
                "closing_balance": statement.closing_balance,
                "total_debits": stats["debits"],
                "total_credits": stats["credits"],
                "pending": stats["pending"],
                "matched": stats["matched"],
                "ignored": stats["ignored"],
                "status": statement.status.value,
                "is_reconciled": statement.status == StatementStatus.RECONCILED,
                "is_balanced": BankingService._is_balanced(
                    statement, stats["debits"], stats["credits"]
                ),
                "computed_closing": BankingService._computed_closing(
                    statement, stats["debits"], stats["credits"]
                ),
            })
        return result

    @staticmethod
    def _computed_closing(statement, debits: Decimal, credits: Decimal):
        if statement.opening_balance is None:
            return None
        return statement.opening_balance + credits - debits

    @staticmethod
    def _is_balanced(statement, debits: Decimal, credits: Decimal) -> bool:
        computed = BankingService._computed_closing(statement, debits, credits)
        return (computed is not None and statement.closing_balance is not None
                and computed == statement.closing_balance)

    @staticmethod
    @transactional
    def get_statement(context: RequestContext, session, statement_id: int) -> dict:
        BankingService._require(context, BankingService.PERM_VIEW)

        statement = session.get(BankStatement, statement_id)
        if statement is None:
            raise ValueError("Statement not found.")
        account = session.get(PaymentAccount, statement.account_id)
        transactions = session.query(BankTransaction).filter(
            BankTransaction.statement_id == statement_id
        ).order_by(BankTransaction.line_no).all()

        invoice_ids = {a.invoice_id for t in transactions for a in t.allocations if a.invoice_id}
        purchase_ids = {a.purchase_id for t in transactions for a in t.allocations if a.purchase_id}
        invoices = {}
        if invoice_ids:
            for invoice, customer_name in session.query(
                Invoice, Customer.company_name
            ).join(Customer, Customer.id == Invoice.customer_id).filter(
                Invoice.id.in_(invoice_ids)
            ).all():
                invoices[invoice.id] = (invoice.invoice_number, customer_name)
        purchases = {}
        if purchase_ids:
            for purchase, supplier_name in session.query(
                Purchase, Supplier.company_name
            ).join(Supplier, Supplier.id == Purchase.supplier_id).filter(
                Purchase.id.in_(purchase_ids)
            ).all():
                purchases[purchase.id] = (purchase.reference, supplier_name)

        tx_rows = []
        pending = matched = ignored = 0
        for transaction in transactions:
            direction = "In" if transaction.credit is not None else "Out"
            allocations = []
            for allocation in transaction.allocations:
                if allocation.invoice_id and allocation.invoice_id in invoices:
                    number, party = invoices[allocation.invoice_id]
                    document_type = "Invoice"
                elif allocation.purchase_id and allocation.purchase_id in purchases:
                    number, party = purchases[allocation.purchase_id]
                    document_type = "Purchase"
                else:
                    number, party = None, None
                    document_type = "Document"
                allocations.append({
                    "id": allocation.id,
                    "document_type": document_type,
                    "invoice_id": allocation.invoice_id,
                    "purchase_id": allocation.purchase_id,
                    "payment_id": allocation.payment_id,
                    "document_number": number,
                    "party": party,
                    "amount": allocation.amount,
                })
            if transaction.status == TransactionStatus.PENDING:
                pending += 1
            elif transaction.status == TransactionStatus.MATCHED:
                matched += 1
            else:
                ignored += 1
            tx_rows.append({
                "id": transaction.id,
                "line_no": transaction.line_no,
                "date": _as_date(transaction.operation_date),
                "value_date": _as_date(transaction.value_date),
                "label": transaction.label,
                "details": transaction.details or "",
                "debit": transaction.debit,
                "credit": transaction.credit,
                "amount": transaction.credit if transaction.credit is not None else transaction.debit,
                "direction": direction,
                "counterparty": transaction.counterparty,
                "rib": transaction.counterparty_rib,
                "reference": transaction.reference,
                "category": transaction.category.value,
                "status": transaction.status.value,
                "match_method": transaction.match_method.value if transaction.match_method else None,
                "match_note": transaction.match_note,
                "allocations": allocations,
            })

        debits = sum((t.debit for t in transactions if t.debit is not None), Decimal("0.00"))
        credits = sum((t.credit for t in transactions if t.credit is not None), Decimal("0.00"))
        computed = BankingService._computed_closing(statement, debits, credits)
        return {
            "statement": {
                "id": statement.id,
                "account_id": statement.account_id,
                "account_name": account.name if account else "",
                "file_name": statement.file_name,
                "bank_profile": statement.bank_profile,
                "account_number": statement.account_number,
                "period_start": _as_date(statement.period_start),
                "period_end": _as_date(statement.period_end),
                "opening_balance": statement.opening_balance,
                "closing_balance": statement.closing_balance,
                "declared_debit_total": statement.declared_debit_total,
                "declared_credit_total": statement.declared_credit_total,
                "total_debits": debits,
                "total_credits": credits,
                "computed_closing": computed,
                "difference": (computed - statement.closing_balance)
                if computed is not None and statement.closing_balance is not None else None,
                "is_balanced": BankingService._is_balanced(statement, debits, credits),
                "status": statement.status.value,
                "is_reconciled": statement.status == StatementStatus.RECONCILED,
                "pending": pending,
                "matched": matched,
                "ignored": ignored,
                "notes": statement.notes,
            },
            "transactions": tx_rows,
        }

    # ------------------------------------------------------------------
    # Categorize / ignore
    # ------------------------------------------------------------------

    @staticmethod
    def _open_statement_transaction(session, transaction_id: int):
        transaction = session.get(BankTransaction, transaction_id)
        if transaction is None:
            raise ValueError("Bank line not found.")
        statement = session.get(BankStatement, transaction.statement_id)
        if statement is None or statement.status != StatementStatus.OPEN:
            raise ValueError("The statement is reconciled; reopen it before editing.")
        return transaction, statement

    @staticmethod
    @transactional
    def set_category(context: RequestContext, session, transaction_id: int,
                     category, counterparty: Optional[str] = None,
                     ignore: Optional[bool] = None) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)
        transaction, _ = BankingService._open_statement_transaction(session, transaction_id)
        if transaction.allocations:
            raise ValueError("This line is already matched; unmatched it first.")

        category = _enum(TransactionCategory, category, "category")
        transaction.category = category
        if counterparty is not None:
            transaction.counterparty = _clean_party(counterparty) if counterparty.strip() else None

        should_ignore = (category in EXPLAINED_CATEGORIES) if ignore is None else bool(ignore)
        transaction.status = (TransactionStatus.IGNORED if should_ignore
                              else TransactionStatus.PENDING)
        transaction.match_method = MatchMethod.MANUAL
        transaction.match_note = "Categorized manually"
        BankingService._remember_counterparty(
            session, transaction.statement.account_id, transaction.counterparty_rib,
            transaction.counterparty,
        )
        session.flush()
        return {"id": transaction.id, "category": category.value,
                "status": transaction.status.value}

    @staticmethod
    @transactional
    def ignore_transaction(context: RequestContext, session, transaction_id: int,
                           ignored: bool = True) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)
        transaction, _ = BankingService._open_statement_transaction(session, transaction_id)
        if transaction.allocations:
            raise ValueError("This line is matched; unmatched it before ignoring it.")
        transaction.status = (TransactionStatus.IGNORED if ignored
                              else TransactionStatus.PENDING)
        transaction.match_method = MatchMethod.MANUAL
        transaction.match_note = "Excluded from reconciliation" if ignored else None
        session.flush()
        return {"id": transaction.id, "status": transaction.status.value}

    @staticmethod
    def _remember_counterparty(session, account_id: int, rib: Optional[str],
                               name: Optional[str], customer_id: Optional[int] = None,
                               supplier_id: Optional[int] = None) -> None:
        if not rib or not name:
            return
        row = session.query(BankCounterparty).filter(
            BankCounterparty.account_id == account_id,
            BankCounterparty.rib == rib,
        ).first()
        if row is None:
            session.add(BankCounterparty(
                account_id=account_id, rib=rib, name=name[:150],
                customer_id=customer_id, supplier_id=supplier_id,
            ))
        else:
            row.name = name[:150]
            if customer_id:
                row.customer_id = customer_id
            if supplier_id:
                row.supplier_id = supplier_id

    # ------------------------------------------------------------------
    # Suggestions and matching
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def suggestions(context: RequestContext, session,
                    transaction_id: int) -> List[dict]:
        BankingService._require(context, BankingService.PERM_VIEW)

        transaction = session.get(BankTransaction, transaction_id)
        if transaction is None:
            raise ValueError("Bank line not found.")
        if transaction.allocations or transaction.status == TransactionStatus.MATCHED:
            return []
        amount = transaction.credit if transaction.credit is not None else transaction.debit
        if amount is None or amount <= 0:
            return []

        text = f"{transaction.label} {transaction.details or ''}"
        rib_memory = None
        if transaction.counterparty_rib:
            rib_memory = session.query(BankCounterparty).filter(
                BankCounterparty.account_id == transaction.statement.account_id,
                BankCounterparty.rib == transaction.counterparty_rib,
            ).first()

        if transaction.credit is not None:
            candidates = BankingService._open_invoices(session)
        else:
            candidates = BankingService._open_purchases(session)

        scored = []
        for candidate in candidates:
            score, reasons = BankingService._score_candidate(
                transaction, amount, candidate, text, rib_memory
            )
            if score >= 25:
                scored.append((score, candidate, reasons))
        scored.sort(key=lambda item: (-item[0], item[1].get("document_date") or date.min))

        results = []
        for score, candidate, reasons in scored[:8]:
            results.append({
                "kind": "document",
                "document_type": candidate["document_type"],
                "invoice_id": candidate.get("invoice_id"),
                "purchase_id": candidate.get("purchase_id"),
                "document_number": candidate["document_number"],
                "party": candidate["party"],
                "document_total": candidate["total"],
                "remaining": candidate["remaining"],
                "document_date": candidate.get("document_date"),
                "score": min(score, 100),
                "reasons": reasons,
                "allocations": [{
                    "invoice_id": candidate.get("invoice_id"),
                    "purchase_id": candidate.get("purchase_id"),
                    "document_number": candidate["document_number"],
                    "party": candidate["party"],
                    "amount": min(amount, candidate["remaining"]),
                }],
            })

        if transaction.credit is not None and (
            transaction.category == TransactionCategory.CUSTOMER_CHEQUE_BATCH
            or "REMISE CHEQUES" in normalize_text(text)
        ):
            batch = BankingService._batch_suggestion(transaction, amount, candidates)
            if batch:
                results.insert(0, batch)
        return results

    @staticmethod
    def _open_invoices(session) -> List[dict]:
        paid = session.query(
            Payment.invoice_id, func.sum(Payment.amount).label("paid")
        ).group_by(Payment.invoice_id).subquery()
        rows = session.query(
            Invoice, Customer.company_name,
            func.coalesce(paid.c.paid, 0),
        ).join(Customer, Customer.id == Invoice.customer_id).outerjoin(
            paid, paid.c.invoice_id == Invoice.id
        ).filter(
            Invoice.state.in_([InvoiceState.VALIDATED, InvoiceState.ISSUED])
        ).all()

        result = []
        for invoice, customer_name, paid_amount in rows:
            total = invoice.total_amount or Decimal("0.00")
            remaining = total - (paid_amount or Decimal("0.00"))
            if remaining <= 0:
                continue
            result.append({
                "document_type": "Invoice",
                "invoice_id": invoice.id,
                "purchase_id": None,
                "document_number": invoice.invoice_number,
                "party": customer_name,
                "total": total,
                "remaining": remaining,
                "document_date": _as_date(invoice.due_date or invoice.created_at),
                "created_date": _as_date(invoice.created_at),
            })
        return result

    @staticmethod
    def _open_purchases(session) -> List[dict]:
        rows = session.query(Purchase, Supplier.company_name).join(
            Supplier, Supplier.id == Purchase.supplier_id
        ).filter(Purchase.state == PurchaseState.VALIDATED).all()
        return [{
            "document_type": "Purchase",
            "invoice_id": None,
            "purchase_id": purchase.id,
            "document_number": purchase.reference,
            "party": supplier_name,
            "total": purchase.total_amount or Decimal("0.00"),
            "remaining": purchase.total_amount or Decimal("0.00"),
            "document_date": _as_date(purchase.created_at),
            "created_date": _as_date(purchase.created_at),
        } for purchase, supplier_name in rows]

    @staticmethod
    def _score_candidate(transaction, amount: Decimal, candidate: dict,
                         text: str, rib_memory) -> tuple:
        score = 0
        reasons = []
        remaining = candidate["remaining"]
        if amount > remaining:
            return 0, []
        if amount == remaining:
            score += 70
            reasons.append("exact outstanding amount")
        elif amount < remaining:
            score += 12
            reasons.append("partial payment")

        name_points = _name_score(transaction.counterparty, candidate["party"])
        if name_points:
            score += name_points
            reasons.append("same counterparty" if name_points >= 27 else "similar name")

        document_date = candidate.get("created_date") or candidate.get("document_date")
        if document_date:
            gap = abs((transaction.operation_date - document_date).days)
            if gap <= 10:
                score += 10
                reasons.append("same period")
            elif gap <= 45:
                score += 6
            elif gap <= 120:
                score += 3

        number = (candidate.get("document_number") or "").lower()
        if number and number in text.lower():
            score += 40
            reasons.append("document number in label")

        if rib_memory:
            if ((candidate["document_type"] == "Invoice" and rib_memory.customer_id)
                    or (candidate["document_type"] == "Purchase" and rib_memory.supplier_id)):
                score += 45
                reasons.append("known RIB")
        return score, reasons

    @staticmethod
    def _batch_suggestion(transaction, amount: Decimal, candidates: List[dict]) -> Optional[dict]:
        invoice_candidates = [
            candidate for candidate in candidates
            if candidate["document_type"] == "Invoice"
            and Decimal("0.00") < candidate["remaining"] <= amount
        ]
        if len(invoice_candidates) < 2:
            return None
        invoice_candidates.sort(
            key=lambda c: abs((transaction.operation_date - c["created_date"]).days)
            if c.get("created_date") else 9999
        )
        invoice_candidates = invoice_candidates[:18]

        values = [int((c["remaining"] * 100).to_integral_value()) for c in invoice_candidates]
        target = int((amount * 100).to_integral_value())
        if sum(values) < target:
            return None
        suffix = [0] * (len(values) + 1)
        for index in range(len(values) - 1, -1, -1):
            suffix[index] = suffix[index + 1] + values[index]

        solution: List[int] = []
        nodes = 0

        def search(index: int, remaining: int, chosen: List[int]) -> bool:
            nonlocal nodes
            nodes += 1
            if remaining == 0:
                solution.extend(chosen)
                return True
            if index >= len(values) or remaining < 0 or suffix[index] < remaining:
                return False
            if nodes > 20000:
                return False
            if search(index + 1, remaining - values[index], chosen + [index]):
                return True
            return search(index + 1, remaining, chosen)

        if not search(0, target, []):
            return None
        chosen = [invoice_candidates[i] for i in solution]
        if len(chosen) < 2:
            return None
        return {
            "kind": "batch",
            "document_type": "Batch",
            "document_number": f"{len(chosen)} invoices",
            "party": None,
            "document_total": amount,
            "remaining": amount,
            "document_date": None,
            "score": 95,
            "reasons": [f"{len(chosen)} open invoices add up exactly"],
            "allocations": [{
                "invoice_id": c["invoice_id"],
                "purchase_id": None,
                "document_number": c["document_number"],
                "party": c["party"],
                "amount": c["remaining"],
            } for c in chosen],
        }

    @staticmethod
    @transactional
    def match(context: RequestContext, session, transaction_id: int,
              allocations: Sequence[dict]) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)

        transaction, statement = BankingService._open_statement_transaction(
            session, transaction_id
        )
        if transaction.allocations:
            raise ValueError("This line is already matched.")
        if not allocations:
            raise ValueError("Select at least one document to match.")

        line_amount = (transaction.credit if transaction.credit is not None
                       else transaction.debit)
        if line_amount is None:
            raise ValueError("The line has no amount.")
        total = Decimal("0.00")
        for allocation in allocations:
            try:
                total += _money(allocation.get("amount"))
            except ValueError:
                raise ValueError("Every allocation needs a valid amount.")
        if total != line_amount:
            raise ValueError(
                f"The selected documents total {total} but the bank line is "
                f"{line_amount}. They must match exactly."
            )

        seen = set()
        invoice_numbers = []
        customer_id = None
        supplier_id = None
        for allocation in allocations:
            invoice_id = allocation.get("invoice_id")
            purchase_id = allocation.get("purchase_id")
            amount = _money(allocation.get("amount"))
            if transaction.credit is not None and not invoice_id:
                raise ValueError("Money received must be matched to an invoice.")
            if transaction.debit is not None and not purchase_id:
                raise ValueError("Money paid out must be matched to a purchase.")
            if invoice_id:
                if invoice_id in seen:
                    raise ValueError("The same invoice was selected twice.")
                seen.add(invoice_id)
                invoice = session.get(Invoice, invoice_id)
                if invoice is None:
                    raise ValueError("Invoice not found.")
                if invoice.state not in (InvoiceState.VALIDATED, InvoiceState.ISSUED):
                    raise ValueError(
                        f"Invoice {invoice.invoice_number} is not open for payment."
                    )
                remaining = SalesService.get_invoice_balance(
                    context, invoice_id, session=session
                )
                if amount > remaining:
                    raise ValueError(
                        f"{amount} exceeds the remaining balance {remaining} of "
                        f"invoice {invoice.invoice_number}."
                    )
                reference = (transaction.reference or transaction.counterparty_rib or "")[:100]
                payment = SalesService.register_payment(
                    context, invoice_id=invoice_id, method="Bank Transfer",
                    amount=amount, reference=reference or None,
                    notes=f"Reconciled from {statement.file_name} line {transaction.line_no}",
                    session=session,
                )
                session.add(BankAllocation(
                    transaction_id=transaction.id, invoice_id=invoice_id,
                    payment_id=payment.id, amount=amount,
                ))
                invoice_numbers.append(invoice.invoice_number)
                customer_id = invoice.customer_id
            elif purchase_id:
                if purchase_id in seen:
                    raise ValueError("The same purchase was selected twice.")
                seen.add(purchase_id)
                purchase = session.get(Purchase, purchase_id)
                if purchase is None:
                    raise ValueError("Purchase not found.")
                if purchase.state != PurchaseState.VALIDATED:
                    raise ValueError("Only validated purchases can be matched.")
                session.add(BankAllocation(
                    transaction_id=transaction.id, purchase_id=purchase_id,
                    amount=amount,
                ))
                invoice_numbers.append(purchase.reference)
                supplier_id = purchase.supplier_id
            else:
                raise ValueError("Each allocation must point at an invoice or a purchase.")

        transaction.status = TransactionStatus.MATCHED
        transaction.match_method = MatchMethod.MANUAL
        transaction.match_note = ("Matched: " + ", ".join(invoice_numbers))[:255]
        if transaction.credit is not None:
            transaction.category = TransactionCategory.CUSTOMER_RECEIPT
        else:
            transaction.category = TransactionCategory.SUPPLIER_PAYMENT
        BankingService._remember_counterparty(
            session, statement.account_id, transaction.counterparty_rib,
            transaction.counterparty, customer_id=customer_id,
            supplier_id=supplier_id,
        )
        session.flush()
        return {
            "id": transaction.id,
            "status": transaction.status.value,
            "allocations": len(allocations),
            "documents": invoice_numbers,
        }

    # ------------------------------------------------------------------
    # Statement lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def reconcile_statement(context: RequestContext, session, statement_id: int,
                            reconciled: bool = True) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)

        statement = session.get(BankStatement, statement_id)
        if statement is None:
            raise ValueError("Statement not found.")
        if not reconciled:
            statement.status = StatementStatus.OPEN
            statement.reconciled_at = None
            session.flush()
            return {"id": statement.id, "status": statement.status.value}

        if statement.status == StatementStatus.RECONCILED:
            return {"id": statement.id, "status": statement.status.value}

        transactions = session.query(BankTransaction).filter(
            BankTransaction.statement_id == statement_id
        ).all()
        pending = [t for t in transactions if t.status == TransactionStatus.PENDING]
        if pending:
            raise ValueError(
                f"{len(pending)} line(s) still need attention. Match them or "
                "mark them as bank fees / excluded first."
            )
        debits = sum((t.debit for t in transactions if t.debit is not None), Decimal("0.00"))
        credits = sum((t.credit for t in transactions if t.credit is not None), Decimal("0.00"))
        if not BankingService._is_balanced(statement, debits, credits):
            raise ValueError(
                "The statement does not balance: opening + money in - money out "
                "does not equal the printed closing balance."
            )
        statement.status = StatementStatus.RECONCILED
        statement.reconciled_at = _now()
        session.flush()
        return {"id": statement.id, "status": statement.status.value}

    @staticmethod
    @transactional
    def delete_statement(context: RequestContext, session, statement_id: int) -> None:
        BankingService._require(context, BankingService.PERM_MANAGE)
        statement = session.get(BankStatement, statement_id)
        if statement is None:
            raise ValueError("Statement not found.")
        if statement.status == StatementStatus.RECONCILED:
            raise ValueError("Reopen the statement before deleting it.")
        matched = session.query(BankAllocation).join(
            BankTransaction, BankTransaction.id == BankAllocation.transaction_id
        ).filter(BankTransaction.statement_id == statement_id).count()
        if matched:
            raise ValueError(
                "This statement has matched lines, so it cannot be deleted. "
                "It would orphan the payments created from it."
            )
        session.delete(statement)
        session.flush()

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    @staticmethod
    @transactional
    def list_rules(context: RequestContext, session) -> List[dict]:
        BankingService._require(context, BankingService.PERM_VIEW)
        rules = session.query(BankRule).order_by(BankRule.priority, BankRule.id).all()
        return [{
            "id": rule.id,
            "name": rule.name,
            "pattern": rule.pattern,
            "direction": rule.direction.value,
            "category": rule.category.value,
            "counterparty": rule.counterparty,
            "priority": rule.priority,
            "is_active": rule.is_active,
        } for rule in rules]

    @staticmethod
    @transactional
    def create_rule(context: RequestContext, session, name: str, pattern: str,
                    category, direction=RuleDirection.ANY,
                    counterparty: Optional[str] = None,
                    priority: int = 100) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)
        name = (name or "").strip()
        pattern = (pattern or "").strip()
        if not name or not pattern:
            raise ValueError("A rule needs a name and a text pattern.")
        if session.query(BankRule).filter(BankRule.name == name).first():
            raise ValueError(f"A rule named '{name}' already exists.")
        category = _enum(TransactionCategory, category, "category")
        direction = _enum(RuleDirection, direction, "direction")
        rule = BankRule(
            name=name, pattern=pattern, category=category, direction=direction,
            counterparty=_clean_party(counterparty) if counterparty else None,
            priority=int(priority),
        )
        session.add(rule)
        session.flush()
        return {"id": rule.id, "name": rule.name}

    @staticmethod
    @transactional
    def set_rule_active(context: RequestContext, session, rule_id: int,
                        active: bool) -> dict:
        BankingService._require(context, BankingService.PERM_MANAGE)
        rule = session.get(BankRule, rule_id)
        if rule is None:
            raise ValueError("Rule not found.")
        rule.is_active = bool(active)
        session.flush()
        return {"id": rule.id, "is_active": rule.is_active}
