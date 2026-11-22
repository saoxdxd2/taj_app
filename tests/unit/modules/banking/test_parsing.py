from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.modules.banking.parsing import (
    StatementParseError,
    file_hash,
    parse_csv,
    parse_fixed_column_lines,
    parse_money,
    parse_statement_file,
)


def tx(day: str, month: str, label: str, amount: str,
       credit: bool = False, value: str = "01 05") -> str:
    """Builds one fixed-column line ending at the right bank column."""
    width = 117 if credit else 95
    body = f"  {day} {month}    {label}"[:66]
    body = body.ljust(66) + value
    return body.ljust(width - 12) + amount.rjust(12)


def solde(amount: str) -> str:
    return f" 30 04    SOLDE".ljust(105) + amount.rjust(12)


HEADER = [
    "1/2           01 05 2026      31 05 2026",
    "011 450  0000462100003065  21",
    "DIRHAM     COMPTES COURANTS COMMERCI                         TAJ FROID",
]


def test_debit_credit_columns_and_wrapped_label():
    lines = HEADER + [
        solde("10 956,00"),
        tx("30", "04", "VIREMENT RECU DE: STE HIGHLIGHT EVENT , MOTIF",
           "14 800,00", credit=True),
        ": VRTFROID SARL , RIB :145450212115046622000484",
        tx("01", "05", "PACKAGE MAI 2026", "108,90"),
        "49 645,90             68 400,00",
        "58 675,10",
    ]
    statement = parse_fixed_column_lines(lines)

    assert statement.period_start == date(2026, 5, 1)
    assert statement.period_end == date(2026, 5, 31)
    assert statement.account_number == "011450000046210000306521"
    assert statement.opening_balance == Decimal("10956.00")
    assert statement.closing_balance == Decimal("58675.10")
    assert len(statement.transactions) == 2
    assert statement.transactions[0].credit == Decimal("14800.00")
    assert statement.transactions[0].debit is None
    assert "VRTFROID SARL" in statement.transactions[0].details
    assert statement.transactions[1].debit == Decimal("108.90")
    assert statement.transactions[1].credit is None
    assert statement.declared_debit_total == Decimal("49645.90")
    assert statement.declared_credit_total == Decimal("68400.00")


def test_balance_mismatch_is_reported_not_hidden():
    lines = HEADER + [
        solde("1 000,00"),
        tx("01", "05", "PACKAGE", "100,00"),
        "100,00             0,00",
        "950,00",
    ]
    statement = parse_fixed_column_lines(lines)
    assert statement.computed_closing == Decimal("900.00")
    assert statement.balanced is False
    assert any("do not add up" in issue for issue in statement.issues())


def test_report_and_page_markers_are_ignored():
    lines = HEADER + [
        solde("1 000,00"),
        tx("01", "05", "PACKAGE", "100,00"),
        "49 645,90             68 400,00",
        "2/2           01 05 2026      31 05 2026",
        "REPORT                       49 645,90             68 400,00",
        tx("02", "05", "COMMISSION", "15,00"),
        "100,00             0,00",
        "885,00",
    ]
    statement = parse_fixed_column_lines(lines)
    assert [t.label for t in statement.transactions] == ["PACKAGE", "COMMISSION"]
    assert statement.balanced is False  # totals printed are not the real ones
    assert any("debit total" in issue for issue in statement.issues())


def test_money_formats():
    assert parse_money("14 800,00") == Decimal("14800.00")
    assert parse_money("108,90") == Decimal("108.90")
    assert parse_money("1 234 567,89") == Decimal("1234567.89")
    assert parse_money("1.234,56") == Decimal("1234.56")
    assert parse_money("") is None
    assert parse_money("not money") is None


def test_csv_with_debit_credit_columns(tmp_path: Path):
    path = tmp_path / "statement.csv"
    path.write_text(
        "Date;Libellé;Débit;Crédit\n"
        "01/05/2026;PACKAGE MAI;108,90;\n"
        "02/05/2026;VIREMENT RECU DE: GMI;;6 000,00\n",
        encoding="utf-8-sig",
    )
    statement = parse_csv(path)

    assert statement.bank_profile == "csv"
    assert len(statement.transactions) == 2
    assert statement.transactions[0].debit == Decimal("108.90")
    assert statement.transactions[1].credit == Decimal("6000.00")
    assert statement.total_debits == Decimal("108.90")
    assert statement.total_credits == Decimal("6000.00")
    assert statement.closing_balance == Decimal("5891.10")


def test_csv_amount_plus_direction(tmp_path: Path):
    path = tmp_path / "statement.csv"
    path.write_text(
        "date,libelle,montant,sens\n"
        "2026-05-01,PACKAGE,108.90,Débit\n"
        "2026-05-02,VIREMENT RECU,6000.00,Crédit\n",
        encoding="utf-8",
    )
    statement = parse_csv(path)

    assert statement.transactions[0].debit == Decimal("108.90")
    assert statement.transactions[1].credit == Decimal("6000.00")


def test_csv_with_preamble_finds_header(tmp_path: Path):
    path = tmp_path / "statement.csv"
    path.write_text(
        "Releve de compte\n"
        "Compte 011450000046210000306521\n"
        "\n"
        "Date operation;Description;Debit;Credit\n"
        "03-05-2026;AGIOS;56,53;\n",
        encoding="utf-8",
    )
    statement = parse_csv(path)
    assert len(statement.transactions) == 1
    assert statement.transactions[0].operation_date == date(2026, 5, 3)


def test_csv_without_header_is_rejected(tmp_path: Path):
    path = tmp_path / "statement.csv"
    path.write_text("01/05/2026;PACKAGE;108,90\n", encoding="utf-8")
    with pytest.raises(StatementParseError):
        parse_csv(path)


def test_pdf_without_text_layer_is_rejected(tmp_path: Path):
    from pypdf import PdfWriter

    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as handle:
        writer.write(handle)

    with pytest.raises(StatementParseError, match="no text layer"):
        parse_statement_file(path)


def test_file_hash_is_stable(tmp_path: Path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"statement-bytes")
    first = file_hash(path)
    assert first == file_hash(path)
    path.write_bytes(b"other")
    assert file_hash(path) != first


REAL_STATEMENTS = sorted(
    (Path(__file__).resolve().parents[4] / "relevée bancaire").glob("*.pdf")
)


@pytest.mark.parametrize("path", REAL_STATEMENTS, ids=lambda p: p.name)
def test_real_statements_reconcile(path: Path):
    statement = parse_statement_file(path)
    assert statement.transactions
    assert statement.balanced, statement.issues()
    assert statement.total_debits == statement.declared_debit_total
    assert statement.total_credits == statement.declared_credit_total
    assert statement.computed_closing == statement.closing_balance
