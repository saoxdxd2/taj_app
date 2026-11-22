"""Parse bank statements into normalized transactions.

Two readers share one normalized result:

* fixed-column PDF text (the layout used by the statements this app was
  built against: date, 56-character label, value date, debit column,
  credit column, wrapped continuation lines);
* CSV with a header row, including the ``montant`` + ``sens`` variant.

Parsing never writes to the database. A statement is only imported after
the caller has verified ``opening + in - out = closing``.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


class StatementParseError(ValueError):
    """The file does not match a supported bank layout."""


MONEY = re.compile(r'^-?\d{1,3}(?: \d{3})*,\d{2}$')
START = re.compile(r'^\s*(\d{2}) (\d{2})\s{2,}')
PERIOD = re.compile(
    r'\b(\d{2}) (\d{2}) (\d{4})\s+(\d{2}) (\d{2}) (\d{4})\b'
)
ACCOUNT = re.compile(r'\b(\d{3} \d{3})\s+(\d{16})\s+(\d{2})\b')
VALUE_DATE_TAIL = re.compile(r'(\d{2}) (\d{2})\s*$')

DEFAULT_FEE_PATTERNS = (
    "COMMISSION", "TVA SUR COMMISSION", "PACKAGE", "AGIOS",
    "PRELEVEMENT", "FRAIS", "BANCASSURANCE", "FPL",
)


@dataclass
class ParsedTransaction:
    operation_date: date
    label: str
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    value_date: Optional[date] = None
    details: str = ""

    @property
    def amount(self) -> Decimal:
        return self.credit if self.credit is not None else (self.debit or Decimal("0.00"))

    @property
    def is_credit(self) -> bool:
        return self.credit is not None


@dataclass
class ParsedStatement:
    bank_profile: str
    transactions: List[ParsedTransaction] = field(default_factory=list)
    account_number: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    declared_debit_total: Optional[Decimal] = None
    declared_credit_total: Optional[Decimal] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def total_debits(self) -> Decimal:
        return sum((t.debit for t in self.transactions if t.debit is not None),
                   Decimal("0.00"))

    @property
    def total_credits(self) -> Decimal:
        return sum((t.credit for t in self.transactions if t.credit is not None),
                   Decimal("0.00"))

    @property
    def computed_closing(self) -> Optional[Decimal]:
        if self.opening_balance is None:
            return None
        return self.opening_balance + self.total_credits - self.total_debits

    @property
    def balanced(self) -> bool:
        """True when every total the file prints agrees with the parsed rows."""
        if self.opening_balance is None or self.closing_balance is None:
            return False
        if self.computed_closing != self.closing_balance:
            return False
        if (self.declared_debit_total is not None
                and self.declared_debit_total != self.total_debits):
            return False
        if (self.declared_credit_total is not None
                and self.declared_credit_total != self.total_credits):
            return False
        return True

    @property
    def balance_difference(self) -> Optional[Decimal]:
        if self.computed_closing is None or self.closing_balance is None:
            return None
        return self.computed_closing - self.closing_balance

    def issues(self) -> List[str]:
        problems = list(self.warnings)
        if self.opening_balance is None:
            problems.append("No opening balance (SOLDE) was found.")
        if self.closing_balance is None:
            problems.append("No closing balance was found.")
        if self.balance_difference:
            problems.append(
                "Parsed transactions do not add up: computed closing "
                f"{self.computed_closing} vs printed {self.closing_balance}."
            )
        if (self.declared_debit_total is not None
                and self.declared_debit_total != self.total_debits):
            problems.append("The printed debit total does not match the parsed debits.")
        if (self.declared_credit_total is not None
                and self.declared_credit_total != self.total_credits):
            problems.append("The printed credit total does not match the parsed credits.")
        return problems


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------

def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_money(text: str) -> Optional[Decimal]:
    text = (text or "").replace("\xa0", " ").strip()
    if not text:
        return None
    cleaned = text.replace(" ", "")
    if cleaned in ("", "-", "--"):
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _date(day: str, month: str, year: int) -> Optional[date]:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _short_date(day: str, month: str, year: int) -> Optional[date]:
    return _date(day, month, year)


def _value_date(text: str, year: int) -> Optional[date]:
    match = VALUE_DATE_TAIL.search(text or "")
    if not match:
        return None
    return _short_date(match.group(1), match.group(2), year)


# ----------------------------------------------------------------------
# Fixed-column PDF layout
# ----------------------------------------------------------------------

_HEADER_SKIP = (
    "DIRHAM", "COMPTES COURANTS", "AUX", "DOM CHEZ", "CONSULTING",
    "MARRAKECH", "LOT ", "HAY ", "MAROC",
)
_PAGE_MARKER = re.compile(r'^\s*\d{1,2}(?:/\d{1,2})?\s')


def _is_page_marker(line: str) -> bool:
    if re.fullmatch(r'\s*\d{1,3}\s*', line):
        return True
    if re.match(r'^\s*\d{1,2}/\d{1,2}\s', line):
        return True
    if line.strip().startswith("*") and line.strip().endswith("*"):
        return True
    if re.match(r'^\s*\d{3} \d{3}\s+\d{16}\s+\d{2}\s*$', line):
        return True
    return False


def parse_fixed_column_lines(lines: Sequence[str]) -> ParsedStatement:
    """Parse the text objects of a fixed-column statement PDF.

    Kept separate from PDF reading so the layout rules are testable with
    plain strings.
    """
    statement = ParsedStatement(bank_profile="fixed-column-v1")
    lines = [line.rstrip("\n") for line in lines if line and line.strip()]
    period = None
    for line in lines:
        found = PERIOD.search(line)
        if found and period is None:
            start = _date(found.group(1), found.group(2), found.group(3))
            end = _date(found.group(4), found.group(5), found.group(6))
            if start and end:
                period = (start, end)
                statement.period_start, statement.period_end = start, end
        account = ACCOUNT.search(line)
        if account and statement.account_number is None:
            statement.account_number = (
                account.group(1) + account.group(2) + account.group(3)
            ).replace(" ", "")

    year = statement.period_end.year if statement.period_end else date.today().year
    closing_candidates: List[Decimal] = []
    last: Optional[ParsedTransaction] = None

    for raw in lines:
        line = raw.rstrip()
        match = START.match(line)
        amount_text = line[-12:].strip() if len(line) >= 80 else ""
        amount = parse_money(amount_text) if MONEY.match(amount_text) else None

        if match and amount is not None:
            day, month = match.group(1), match.group(2)
            operation = _short_date(day, month, year)
            if operation is None:
                raise StatementParseError(f"Invalid transaction date in: {line!r}")

            tail = line[match.end():len(line) - 12]
            value_match = VALUE_DATE_TAIL.search(tail)
            if value_match:
                label = tail[:value_match.start()].strip()
                value = _short_date(value_match.group(1), value_match.group(2), year)
            else:
                label = tail.strip()
                value = None

            is_credit = len(line) > 106
            if label.upper().startswith("SOLDE"):
                if statement.opening_balance is None:
                    statement.opening_balance = amount
                else:
                    closing_candidates.append(amount)
                last = None
                continue

            transaction = ParsedTransaction(
                operation_date=operation,
                value_date=value,
                label=re.sub(r'\s{2,}', ' ', label),
                debit=None if is_credit else amount,
                credit=amount if is_credit else None,
            )
            statement.transactions.append(transaction)
            last = transaction
            continue

        if not match and "REPORT" in line[:40]:
            last = None
            continue

        # Page and statement totals: exactly two amounts, nothing else.
        if not match and len(line) > 30:
            totals = re.fullmatch(
                r'\s*\d{1,3}(?: \d{3})*,\d{2}\s+\d{1,3}(?: \d{3})*,\d{2}\s*',
                line,
            )
            if totals:
                tokens = re.findall(r'\d{1,3}(?: \d{3})*,\d{2}', line)
                debit_total = parse_money(tokens[0])
                credit_total = parse_money(tokens[1])
                if debit_total is not None and credit_total is not None:
                    statement.declared_debit_total = debit_total
                    statement.declared_credit_total = credit_total
                    last = None
                    continue

        if not match and MONEY.match(line.strip()):
            balance = parse_money(line.strip())
            if balance is not None:
                closing_candidates.append(balance)
            last = None
            continue

        if _is_page_marker(line) or any(token in line for token in _HEADER_SKIP):
            last = None
            continue

        stripped = line.strip()
        if last is not None and stripped:
            last.details = (last.details + " " + stripped).strip()

    if closing_candidates:
        statement.closing_balance = closing_candidates[-1]
    elif statement.transactions:
        statement.closing_balance = statement.computed_closing
        statement.warnings.append("The statement did not print a closing balance.")
    if statement.declared_debit_total is None and statement.transactions:
        statement.declared_debit_total = statement.total_debits
        statement.declared_credit_total = statement.total_credits
        statement.warnings.append("The statement did not print debit/credit totals.")

    return statement


def _pdf_text_lines(path: Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise StatementParseError(
            "PDF support is not installed (pypdf). Use a CSV export instead."
        ) from exc

    reader = PdfReader(str(path))
    lines: List[str] = []
    for page in reader.pages:
        objects: List[str] = []

        def collect(text, cm, tm, font, size):
            if text and text.strip():
                objects.append(text)

        page.extract_text(visitor_text=collect)
        for block in objects:
            lines.extend(block.splitlines())
    return lines


def parse_pdf(path: Path) -> ParsedStatement:
    lines = _pdf_text_lines(path)
    if not any(any(char.isalpha() for char in line) for line in lines):
        raise StatementParseError(
            "This PDF has no text layer (it is a scan or a photo). "
            "Download the digital PDF from your bank, or use a CSV export."
        )
    if not any("SOLDE" in line.upper() or START.match(line) for line in lines):
        raise StatementParseError(
            "This PDF does not look like a bank statement in a supported layout."
        )
    return parse_fixed_column_lines(lines)


# ----------------------------------------------------------------------
# CSV
# ----------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
                 "%d/%m/%y", "%d-%m-%y")


def parse_csv_date(text: str) -> Optional[date]:
    text = (text or "").strip()
    if not text:
        return None
    for candidate in (text, text.split(" ")[0], text.split("T")[0]):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


_HEADER_ALIASES = {
    "date": ("date", "date operation", "date de l operation", "operation date"),
    "value_date": ("date valeur", "value date"),
    "label": ("libelle", "libelle operation", "description", "label", "motif",
              "nature", "details"),
    "debit": ("debit", "sortie", "out", "withdrawal", "retrait"),
    "credit": ("credit", "entree", "in", "deposit", "versement"),
    "amount": ("montant", "amount", "valeur"),
    "direction": ("sens", "type", "direction", "operation"),
}


def _header_map(row: Sequence[str]) -> dict:
    normalized = [_normalize(cell) for cell in row]
    mapping = {}
    for field_name, aliases in _HEADER_ALIASES.items():
        for index, cell in enumerate(normalized):
            if cell in aliases:
                mapping[field_name] = index
                break
    return mapping


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise StatementParseError("The CSV file encoding is not supported.")


def parse_csv(path: Path) -> ParsedStatement:
    text = _read_text(path)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","

    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise StatementParseError("The CSV file is empty.")

    header_index = None
    mapping = {}
    for index, row in enumerate(rows[:20]):
        candidate = _header_map(row)
        if "date" in candidate and (
            "debit" in candidate or "credit" in candidate or "amount" in candidate
        ):
            header_index = index
            mapping = candidate
            break
    if header_index is None:
        raise StatementParseError(
            "No header row with a date and debit/credit (or amount) was found. "
            "Export the statement with a header row, or add it in Excel."
        )

    statement = ParsedStatement(bank_profile="csv")
    for line_no, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        def cell(name: str) -> str:
            index = mapping.get(name)
            if index is None or index >= len(row):
                return ""
            return row[index].strip()

        if not any(value.strip() for value in row):
            continue
        operation = parse_csv_date(cell("date"))
        if operation is None:
            # Ignore trailing summary rows rather than losing real rows.
            if not (cell("debit") or cell("credit") or cell("amount")):
                continue
            raise StatementParseError(
                f"Line {line_no}: cannot read the date {cell('date')!r}."
            )
        label = cell("label") or cell("direction") or "Bank line"
        debit = parse_money(cell("debit"))
        credit = parse_money(cell("credit"))
        if debit is None and credit is None:
            amount = parse_money(cell("amount"))
            if amount is None:
                continue
            direction = _normalize(cell("direction"))
            is_debit = direction in ("d", "debit") or any(
                word in direction for word in
                ("debit", "sortie", "out", "retrait", "withdrawal")
            )
            if is_debit or amount < 0:
                debit = abs(amount)
            else:
                credit = abs(amount)
        statement.transactions.append(ParsedTransaction(
            operation_date=operation,
            value_date=parse_csv_date(cell("value_date")),
            label=label,
            debit=debit,
            credit=credit,
        ))

    if not statement.transactions:
        raise StatementParseError("No transaction rows were found in the CSV file.")
    statement.warnings.append(
        "CSV files do not include an opening balance; the closing balance "
        "was computed from zero."
    )
    statement.opening_balance = Decimal("0.00")
    statement.closing_balance = statement.computed_closing
    statement.declared_debit_total = statement.total_debits
    statement.declared_credit_total = statement.total_credits
    return statement


def parse_statement_file(path) -> ParsedStatement:
    path = Path(path)
    if not path.is_file():
        raise StatementParseError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".csv", ".txt"):
        return parse_csv(path)
    raise StatementParseError(
        "Only PDF and CSV statements are supported. "
        "Export the statement as PDF or CSV from your bank."
    )
