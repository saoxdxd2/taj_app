"""Golden-file tests for the supplier invoice extractor.

Each fixture is real Windows OCR output (word + bounding box) captured from a
supplier paper in ``img/``. The expected values below are what a human reads on
the paper, so a regression here means the extractor stopped matching reality.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.modules.purchasing.invoice_extraction import Word, extract_invoice

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "invoice_ocr"


def _load(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    words = [
        Word(text=word["t"], x=word["x"], y=word["y"], width=word["w"], height=word["h"])
        for word in data["words"]
    ]
    return data["width"], data["height"], words


def _extract(name):
    width, height, words = _load(name)
    return extract_invoice(width, height, words)


EXPECTED = [
    pytest.param(
        "tcl",
        "9660007552",
        date(2026, 9, 22),
        "003947029000043",
        [(2, "2274.35", "4548.70"), (14, "3444.35", "48220.90"), (10, "4159.35", "41593.50")],
        ("94363.10", "18872.62", "113235.72"),
        "0.00",
        id="tcl",
    ),
    pytest.param(
        "bati",
        "FM2601900",
        date(2026, 5, 12),
        "001733780000043",
        [(4, "132.80", "531.20"), (4, "120.75", "483.00")],
        ("1014.20", "202.84", "1220.08"),
        "0.00",
        id="bati",
    ),
    pytest.param(
        "ariha",
        "FA26003036",
        date(2026, 5, 12),
        "003947029000043",
        [(1, "0.00", "0.00"), (1, "9000.00", "9000.00")],
        ("9000.00", "1800.00", "10800.00"),
        "0.00",
        id="ariha",
    ),
    pytest.param(
        "electro",
        "FA12678-2026",
        date(2026, 9, 25),
        "002572535000054",
        [(1, "1900.00", "1900.00"), (2, "11500.00", "23000.00")],
        ("24900.00", "4600.00", "29500.00"),
        "0.00",
        id="electro",
    ),
]


@pytest.mark.parametrize(
    "name, invoice_number, invoice_date, ice, lines, totals, carried", EXPECTED
)
def test_extracts_paper_values(name, invoice_number, invoice_date, ice, lines, totals, carried):
    invoice = _extract(name)

    assert invoice.warnings == []
    assert invoice.invoice_number == invoice_number
    assert invoice.invoice_date == invoice_date
    assert invoice.supplier_ice == ice
    assert len(invoice.lines) == len(lines)
    for extracted, (quantity, unit_cost, amount) in zip(invoice.lines, lines):
        assert extracted.quantity == quantity
        assert extracted.unit_cost == Decimal(unit_cost)
        assert extracted.amount == Decimal(amount)
    assert (invoice.total_ht, invoice.total_tva, invoice.total_ttc) == tuple(
        Decimal(value) for value in totals
    )
    assert invoice.carried_amount == Decimal(carried)


def test_easydis_six_lines_and_carried_report():
    invoice = _extract("easydis")

    assert invoice.warnings == []
    assert invoice.invoice_number == "26FA08217"
    assert invoice.invoice_date == date(2026, 6, 19)
    assert invoice.supplier_ice == "003947029000043"
    assert len(invoice.lines) == 6
    assert invoice.carried_amount == Decimal("179155.79")
    # The report carries the running total of paper 1; both parts make the HT.
    assert invoice.carried_amount + sum(line.amount for line in invoice.lines) == Decimal("232613.39")
    assert (invoice.total_ht, invoice.total_tva, invoice.total_ttc) == (
        Decimal("232613.39"),
        Decimal("46522.66"),
        Decimal("279136.05"),
    )


def test_line_arithmetic_agrees_with_paper():
    # BATI also prints a 3.04 D.TIMBRE (stamp duty) between TVA and TTC.
    timbre = {"tcl": Decimal("0"), "bati": Decimal("3.04"),
              "ariha": Decimal("0"), "electro": Decimal("0")}
    for name in timbre:
        invoice = _extract(name)
        for line in invoice.lines:
            assert line.quantity * line.unit_cost == line.amount
        assert sum(line.amount for line in invoice.lines) == invoice.total_ht
        assert invoice.total_ht + invoice.total_tva + timbre[name] == invoice.total_ttc


def test_columns_are_exported_as_page_fractions():
    invoice = _extract("tcl")

    assert invoice.fingerprint
    assert "amount" in invoice.columns
    for left, right in invoice.columns.values():
        assert 0.0 <= left <= 1.0
        assert 0.0 <= right <= 1.0
        assert left < right
