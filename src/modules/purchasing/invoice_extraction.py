"""Reading a scanned supplier invoice into structured purchase lines.

OCR only turns pixels into words. This module rebuilds the table from word
positions: it finds the header row, maps the French column labels to canonical
fields, groups words into rows, and validates the arithmetic of the paper.

Supplier layouts differ, so nothing here is hard-coded per supplier. When a
layout is confirmed once, the caller can store the discovered column ranges in
a :class:`SupplierInvoiceProfile` and pass them back through ``profile`` on
later imports.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.modules.banking.parsing import parse_money


@dataclass(frozen=True)
class Word:
    text: str
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2


@dataclass
class Row:
    cy: float
    words: List[Word]


@dataclass
class ExtractedLine:
    reference: str
    label: str
    quantity: int
    unit_cost: Decimal
    amount: Decimal


@dataclass
class ExtractedInvoice:
    invoice_number: str = ""
    invoice_date: Optional[date] = None
    supplier_ice: str = ""
    lines: List[ExtractedLine] = field(default_factory=list)
    total_ht: Optional[Decimal] = None
    total_tva: Optional[Decimal] = None
    total_ttc: Optional[Decimal] = None
    carried_amount: Decimal = Decimal("0.00")
    warnings: List[str] = field(default_factory=list)
    text: str = ""
    fingerprint: str = ""
    columns: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class _Phrase:
    words: List[Word]

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @property
    def x0(self) -> float:
        return min(word.x for word in self.words)

    @property
    def x1(self) -> float:
        return max(word.x2 for word in self.words)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().replace("&", " ET ")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text)).strip()


def _compact(text: str) -> str:
    return _fold(text).replace(" ", "")


def _is_date_token(text: str) -> bool:
    folded = _fold(text)
    return bool(
        re.fullmatch(r"\d{1,2} \d{1,2} \d{2,4}", folded)
        or re.fullmatch(r"\d{4} \d{1,2} \d{1,2}", folded)
    )


_NUMERIC_CHARS = re.compile(r"[0-9oO.,%+\- ]+")


def _looks_numeric(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or _is_date_token(raw):
        return False
    if not re.search(r"[0-9]", raw) and not re.fullmatch(r"[oO.,]+", raw):
        return False
    return bool(_NUMERIC_CHARS.fullmatch(raw))


def _numeric_text(text: str) -> str:
    """Repairs the digit confusions Windows OCR makes inside a numeric cell."""
    text = (text or "").replace("\u00a0", " ").strip()
    if re.search(r"[0-9]", text):
        text = text.replace("o", "0").replace("O", "0")
        text = re.sub(r"(?<=\d)[lI](?=\d)", "1", text)
        text = re.sub(r"%$", "0", text)
    elif re.fullmatch(r"[oO.,\s]+", text):
        text = text.replace("o", "0").replace("O", "0")
    return text.strip()


def _money(text: str) -> Optional[Decimal]:
    return parse_money(_numeric_text(text))


def _rows(words: Sequence[Word]) -> List[Row]:
    if not words:
        return []
    heights = sorted(word.height for word in words if word.height)
    tolerance = max(6.0, (heights[len(heights) // 2] if heights else 10) * 0.7)
    rows: List[Row] = []
    for word in sorted(words, key=lambda item: item.cy):
        if rows and abs(rows[-1].cy - word.cy) <= tolerance:
            rows[-1].words.append(word)
            rows[-1].cy = sum(w.cy for w in rows[-1].words) / len(rows[-1].words)
        else:
            rows.append(Row(cy=word.cy, words=[word]))
    for row in rows:
        row.words.sort(key=lambda item: item.x)
    return rows


def _phrases(row: Row, page_width: float) -> List[_Phrase]:
    gap_limit = max(8.0, page_width * 0.009)
    phrases: List[_Phrase] = []
    for word in row.words:
        if phrases and word.x - phrases[-1].words[-1].x2 <= gap_limit:
            phrases[-1].words.append(word)
        else:
            phrases.append(_Phrase(words=[word]))
    return phrases


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def _header_field(text: str) -> Optional[str]:
    compact = _compact(text)
    words = set(_fold(text).split())
    if not compact:
        return None
    if words & {"UNITE", "SOURCE", "REMISE", "ESCOMPTE"}:
        return "ignore"
    if words & {"QTE", "QUANTITE", "QTY"}:
        return "quantity"
    if words & {"REFERENCE", "REF", "CODE", "MODELE"}:
        return "reference"
    if words & {"DESIGNATION", "DESCRIPTION", "ARTICLES", "ARTICLE", "LIBELLE"}:
        return "label"
    if "TVA" in words:
        return None
    if "PU" in compact or "PRIX" in compact or "UNITAIRE" in compact:
        return "unit_ttc" if "TTC" in compact else "unit_cost"
    if "MONTANT" in compact or "MT" in words:
        return "amount_ttc" if "TTC" in compact else "amount"
    return None


def _find_header(rows: Sequence[Row], page_width: float) -> Tuple[Optional[int], List[Tuple[str, _Phrase]]]:
    best_index: Optional[int] = None
    best_score = 0
    best_fields: List[Tuple[str, _Phrase]] = []
    for index, row in enumerate(rows):
        fields = [(kind, phrase) for phrase in _phrases(row, page_width)
                  for kind in [_header_field(phrase.text)] if kind]
        score = len({kind for kind, _ in fields if kind != "ignore"})
        if score > best_score:
            best_index, best_score, best_fields = index, score, fields
    if best_score < 2:
        return None, []
    return best_index, best_fields


# ---------------------------------------------------------------------------
# Column geometry
# ---------------------------------------------------------------------------

@dataclass
class _Column:
    words: List[Word] = field(default_factory=list)

    @property
    def cx(self) -> float:
        return sum(word.cx for word in self.words) / len(self.words)

    @property
    def x0(self) -> float:
        return min(word.x for word in self.words)

    @property
    def x1(self) -> float:
        return max(word.x2 for word in self.words)


def _cluster_columns(words: Iterable[Word], gap_limit: float,
                     by_center: bool = False) -> List[_Column]:
    ordered = sorted(words, key=lambda word: word.cx if by_center else word.x)
    columns: List[_Column] = []
    for word in ordered:
        if columns:
            last = columns[-1].words[-1]
            gap = (word.cx - last.cx) if by_center else (word.x - last.x2)
            if gap <= gap_limit:
                columns[-1].words.append(word)
                continue
        columns.append(_Column(words=[word]))
    return columns


def _nearest(columns: Sequence[_Column], cx: float) -> Optional[int]:
    if not columns:
        return None
    return min(range(len(columns)), key=lambda index: abs(columns[index].cx - cx))


# ---------------------------------------------------------------------------
# Dates and numbers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[\s/.\-](\d{1,2})[\s/.\-](\d{2,4})(?!\d)")
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)")
# Scanners often read the slashes of 12/05/26 as ones: 12105126.
_OCR_SLASH_DATE_RE = re.compile(r"^(\d{2})[1lI](\d{2})[1lI](\d{2,4})$")


def _to_date(raw: str) -> Optional[date]:
    stored = (raw or "").strip()
    match = _ISO_DATE_RE.search(stored)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = _OCR_SLASH_DATE_RE.fullmatch(stored)
    if match:
        day, month, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = _DATE_RE.search(stored)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _find_date(rows: Sequence[Row], page_height: float) -> Optional[date]:
    for index, row in enumerate(rows):
        folded = _fold(" ".join(word.text for word in row.words))
        if "DATE" not in folded or "ECHEANCE" in folded:
            continue
        for candidate in [row] + list(rows[index + 1:index + 3]):
            for word in candidate.words:
                found = _to_date(word.text)
                if found:
                    return found
    for row in rows:
        if row.cy > page_height * 0.45:
            break
        for word in row.words:
            found = _to_date(word.text)
            if found:
                return found
    return None


_INVOICE_RE = re.compile(r"^(?=.*\d)[A-Z0-9][A-Z0-9/\-]{3,}$")
_SKIP_WORDS = {"FACTURE", "NUMERO", "DATE", "CLIENT", "NO", "N", "BC", "DE", "DU"}


def _find_invoice_number(rows: Sequence[Row], header_index: Optional[int]) -> str:
    limit = header_index if header_index is not None else len(rows)
    same_row: List[str] = []
    nearby: List[str] = []
    for index, row in enumerate(rows[: max(limit, 1) + 4]):
        folded = _fold(" ".join(word.text for word in row.words))
        if not any(key in folded for key in ("FACTURE", "NUMERO")):
            continue
        for offset, candidate in enumerate([row] + list(rows[index + 1:index + 3])):
            bucket = same_row if offset == 0 else nearby
            for word in candidate.words:
                for piece in re.split(r"[:;]", word.text):
                    token = piece.strip().strip(".,()[]").replace(" ", "")
                    folded_token = _fold(token)
                    if not token or _is_date_token(token) or folded_token in _SKIP_WORDS:
                        continue
                    if _INVOICE_RE.fullmatch(token.upper()) and len(re.sub(r"\D", "", token)) != 15:
                        bucket.append(token.upper())

    def preferred(tokens: List[str]) -> str:
        # A prefixed number (FA26003036) beats a bare client code sitting
        # between the "FACTURE" label and the real number.
        for token in tokens:
            if re.search(r"[A-Z]", token):
                return token
        return tokens[0] if tokens else ""

    return preferred(same_row) or preferred(nearby)


_ICE_RE = re.compile(r"I\s*\.?\s*C\s*\.?\s*E\s*[:;]?\s*([0-9 ]{12,20})", re.IGNORECASE)


def _find_ice(rows: Sequence[Row]) -> str:
    joined = "\n".join(" ".join(word.text for word in row.words) for row in rows)
    match = _ICE_RE.search(joined)
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(1))
    return digits[:15] if len(digits) >= 9 else ""


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

def _numeric_groups(words: Sequence[Word], page_width: float) -> List[Tuple[float, str]]:
    limit = max(18.0, page_width * 0.010)
    ordered = sorted((word for word in words if _looks_numeric(word.text)), key=lambda word: word.x)
    groups: List[List[Word]] = []
    for word in ordered:
        if groups and word.x - groups[-1][-1].x2 <= limit:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [((group[0].x + group[-1].x2) / 2, " ".join(word.text for word in group)) for group in groups]


def _totals_field(text: str) -> Optional[str]:
    compact = _compact(text)
    if "TTC" in compact and ("TOTAL" in compact or "MT" in compact or "NET" in compact):
        return "total_ttc"
    if "HT" in compact and ("TOTAL" in compact or "MT" in compact):
        return "total_ht"
    if "TVA" in compact:
        return "total_tva"
    if "NET" in compact and "PAYER" in compact:
        return "total_ttc"
    return None


def _row_total_labels(row: Row, page_width: float) -> List[Tuple[float, str]]:
    phrases = _phrases(row, page_width)
    labels: List[Tuple[float, str]] = []
    index = 0
    while index < len(phrases):
        matched = False
        for span in (3, 2, 1):
            if index + span > len(phrases):
                continue
            text = " ".join(phrase.text for phrase in phrases[index:index + span])
            field_name = _totals_field(text)
            if field_name:
                center = (phrases[index].x0 + phrases[index + span - 1].x1) / 2
                labels.append((center, field_name))
                index += span
                matched = True
                break
        if not matched:
            index += 1
    return labels


def _consistent_totals(values: Sequence[Decimal]) -> Optional[Tuple[Decimal, Decimal, Decimal]]:
    unique = sorted(set(value for value in values if value > 0))
    best = None
    best_key = None
    for ttc in unique:
        for ht in unique:
            if ht >= ttc:
                continue
            for tva in unique:
                extra = ttc - ht - tva
                if extra < 0 or extra > max(Decimal("10.00"), ttc * Decimal("0.01")):
                    continue
                key = (ttc, 1 if tva > 0 else 0, -abs(tva - ht * Decimal("0.2")))
                if best_key is None or key > best_key:
                    best, best_key = (ht, tva, ttc), key
    return best


def _totals_agree(ht: Optional[Decimal], tva: Optional[Decimal],
                  ttc: Optional[Decimal]) -> bool:
    if ht is None or tva is None or ttc is None:
        return False
    return abs(ht + tva - ttc) <= max(Decimal("0.10"), ttc * Decimal("0.002"))


def _find_totals(rows: Sequence[Row], start: int,
                 page_width: float) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    found: Dict[str, Decimal] = {}
    values: List[Decimal] = []
    labels: List[Tuple[float, str]] = []
    for row in rows[start:start + 3]:
        row_labels = _row_total_labels(row, page_width)
        if row_labels:
            labels = row_labels
        for cx, text in _numeric_groups(row.words, page_width):
            value = _money(text)
            if value is None:
                continue
            values.append(value)
            if not labels:
                continue
            _, field_name = min(labels, key=lambda item: abs(item[0] - cx))
            if field_name not in found:
                found[field_name] = value

    ht, tva, ttc = found.get("total_ht"), found.get("total_tva"), found.get("total_ttc")
    if not _totals_agree(ht, tva, ttc):
        best = _consistent_totals(values)
        if best is not None:
            ht, tva, ttc = best
    return ht, tva, ttc


def _is_totals_row(row: Row) -> bool:
    folded = _fold(" ".join(word.text for word in row.words))
    keys = ("TOTAL", "TVA", "NET A PAYER", "ACOMPTE", "ESCOMPTE", "TIMBRE", "ARRETEE", "RECAPITULATIF")
    return any(key in folded for key in keys)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_invoice(page_width: float, page_height: float, words: Sequence[Word],
                    profile: Optional[dict] = None) -> ExtractedInvoice:
    rows = _rows(words)
    invoice = ExtractedInvoice(text="\n".join(" ".join(word.text for word in row.words) for row in rows))
    header_index, header_fields = _find_header(rows, page_width)
    if header_index is None:
        invoice.warnings.append("Could not find the invoice table header (Référence/Désignation/Qté).")
        return invoice

    header_phrases = _phrases(rows[header_index], page_width)
    invoice.fingerprint = hashlib.sha1("|".join(sorted(_compact(p.text) for p in header_phrases)).encode()).hexdigest()

    end_index = len(rows)
    for index in range(header_index + 1, len(rows)):
        if _is_totals_row(rows[index]) or _row_total_labels(rows[index], page_width):
            end_index = index
            break
    body_rows = rows[header_index + 1:end_index]
    body_words = [word for row in body_rows for word in row.words]

    text_roles: Dict[str, _Phrase] = {}
    numeric_phrases: Dict[str, _Phrase] = {}
    ignore_ranges: List[Tuple[float, float]] = []
    for kind, phrase in header_fields:
        if kind in ("reference", "label"):
            text_roles.setdefault(kind, phrase)
        elif kind == "ignore":
            ignore_ranges.append((phrase.x0, phrase.x1))
        elif kind not in numeric_phrases:
            numeric_phrases[kind] = phrase

    # Body words decide the real column positions: header labels can be
    # centred over a wide column while the values start at its left edge.
    gap_limit = max(18.0, page_width * 0.010)
    numeric_words = [word for word in body_words if _looks_numeric(word.text)]
    columns = _cluster_columns(numeric_words, gap_limit)

    roles: Dict[str, int] = {}
    for kind, phrase in numeric_phrases.items():
        index = _nearest(columns, phrase.cx)
        if index is not None:
            roles[kind] = index

    column_bounds: Dict[str, Tuple[float, float]] = {}
    for kind, index in roles.items():
        column = columns[index]
        column_bounds[kind] = (column.x0 - gap_limit / 2, column.x1 + gap_limit / 2)

    if "reference" in text_roles:
        header = text_roles["reference"]
        reference_bounds: Optional[Tuple[float, float]] = (
            max(0.0, header.x0 - page_width * 0.03),
            header.cx + page_width * 0.04,
        )
    else:
        reference_bounds = None

    if columns:
        first_numeric_x = min((columns[index].x0 for index in roles.values()),
                              default=columns[0].x0)
    else:
        first_numeric_x = page_width

    if reference_bounds is not None:
        label_bounds: Optional[Tuple[float, float]] = (
            reference_bounds[1] + page_width * 0.004,
            first_numeric_x - page_width * 0.015,
        )
    else:
        label_bounds = (0.0, first_numeric_x - page_width * 0.015)

    if profile and profile.get("columns"):
        for name, (x0, x1) in profile["columns"].items():
            left, right = x0 * page_width, x1 * page_width
            if name == "reference":
                reference_bounds = (left, right)
            elif name == "label":
                label_bounds = (left, right)
            elif name == "ignore":
                ignore_ranges.append((left, right))
            elif name in ("quantity", "unit_cost", "unit_ttc", "amount", "amount_ttc"):
                column_bounds[name] = (left, right)

    amount_field = "amount" if "amount" in column_bounds else ("amount_ttc" if "amount_ttc" in column_bounds else None)
    if amount_field is None:
        invoice.warnings.append("Could not identify the amount column.")
        return invoice

    def in_ignore(cx: float) -> bool:
        return any(left - 4 <= cx <= right + 4 for left, right in ignore_ranges)

    def text_cell(row: Row, bounds: Optional[Tuple[float, float]]) -> str:
        if bounds is None:
            return ""
        left, right = bounds
        return " ".join(word.text for word in row.words if left <= word.cx <= right and not in_ignore(word.cx))

    def cell_value(row: Row, bounds: Optional[Tuple[float, float]]) -> Optional[Decimal]:
        if bounds is None:
            return None
        left, right = bounds
        text = " ".join(word.text for word in row.words
                        if left <= word.cx <= right and _looks_numeric(word.text))
        return _money(text) if text else None

    qty_field = "quantity" if "quantity" in column_bounds else None
    unit_field = "unit_cost" if "unit_cost" in column_bounds else ("unit_ttc" if "unit_ttc" in column_bounds else None)

    # Pick the price column by arithmetic: layouts sometimes hide it or label a
    # TTC price while the amount column we read is HT.
    amount_bounds = column_bounds[amount_field]
    qty_bounds = column_bounds.get(qty_field) if qty_field else None

    def score_unit(bounds: Tuple[float, float]) -> int:
        score = 0
        for row in body_rows:
            amount = cell_value(row, amount_bounds)
            quantity = cell_value(row, qty_bounds) if qty_bounds else None
            unit = cell_value(row, bounds)
            if amount is None or quantity is None or unit is None or quantity == 0:
                continue
            if abs(quantity * unit - amount) <= max(Decimal("0.05"), abs(amount) * Decimal("0.01")):
                score += 1
        return score

    candidates: List[Tuple[str, Tuple[float, float]]] = []
    if unit_field is not None:
        candidates.append((unit_field, column_bounds[unit_field]))
    used = set(roles.values())
    for index, column in enumerate(columns):
        if index in used:
            continue
        candidates.append(("unit_cost", (column.x0 - gap_limit / 2, column.x1 + gap_limit / 2)))

    best_name, best_bounds, best_score = None, None, 0
    for name, bounds in candidates:
        score = score_unit(bounds)
        is_current = unit_field is not None and bounds == column_bounds.get(unit_field)
        if score > best_score or (score == best_score and is_current):
            best_name, best_bounds, best_score = name, bounds, score
    if best_name is not None and best_score > 0:
        if unit_field and unit_field != best_name:
            column_bounds.pop(unit_field, None)
        column_bounds[best_name] = best_bounds
        unit_field = best_name

    row_ys = [row.cy for row in body_rows]
    typical_gap = 40.0
    if len(row_ys) > 1:
        gaps = sorted(second - first for first, second in zip(row_ys, row_ys[1:]) if second > first)
        if gaps:
            typical_gap = gaps[len(gaps) // 2]

    previous: Optional[ExtractedLine] = None
    previous_y: Optional[float] = None
    for row in body_rows:
        folded = _fold(" ".join(word.text for word in row.words))
        amount = cell_value(row, column_bounds[amount_field])
        qty_value = cell_value(row, column_bounds[qty_field]) if qty_field else None
        unit = cell_value(row, column_bounds[unit_field]) if unit_field else None

        if sum(value is not None for value in (amount, qty_value, unit)) < 2:
            if previous is not None and previous_y is not None and row.cy - previous_y <= typical_gap * 1.8:
                extra = text_cell(row, label_bounds)
                if extra:
                    previous.label = (previous.label + " " + extra).strip()
                    previous_y = row.cy
            continue

        if amount is None and qty_value is not None and unit is not None:
            amount = (qty_value * unit).quantize(Decimal("0.01"))
        if qty_value is None and amount is not None and unit not in (None, Decimal("0")):
            qty_value = (amount / unit).quantize(Decimal("1"))

        if "REPORT" in folded:
            invoice.carried_amount += amount or Decimal("0.00")
            previous = None
            previous_y = row.cy
            continue

        reference = text_cell(row, reference_bounds).strip()
        label = text_cell(row, label_bounds).strip()
        quantity_decimal = qty_value if qty_value is not None else Decimal("1")
        if unit is None and amount is not None and quantity_decimal:
            unit = (amount / quantity_decimal).quantize(Decimal("0.01"))
        if amount is None:
            amount = (quantity_decimal * (unit or Decimal("0.00"))).quantize(Decimal("0.01"))
        quantity = int(quantity_decimal.to_integral_value())
        if quantity_decimal != quantity:
            invoice.warnings.append(f"Line '{label[:40]}': fractional quantity {quantity_decimal} rounded to {quantity}.")
        if quantity <= 0:
            continue
        unit = unit or Decimal("0.00")
        line_total = (Decimal(quantity) * unit).quantize(Decimal("0.01"))
        tax_mismatch = (
            (amount_field == "amount" and unit_field == "unit_ttc")
            or (amount_field == "amount_ttc" and unit_field == "unit_cost")
        )
        if not tax_mismatch and abs(line_total - amount) > max(Decimal("0.05"), amount * Decimal("0.01")):
            invoice.warnings.append(
                f"Line '{label[:40]}': {quantity} x {unit} = {line_total}, paper says {amount}."
            )
        invoice.lines.append(ExtractedLine(
            reference=reference,
            label=label or reference,
            quantity=quantity,
            unit_cost=unit,
            amount=amount,
        ))
        previous = invoice.lines[-1]
        previous_y = row.cy

    if not invoice.lines:
        invoice.warnings.append("No invoice lines were recognized.")

    total_ht, total_tva, total_ttc = _find_totals(rows, end_index, page_width)
    invoice.total_ht, invoice.total_tva, invoice.total_ttc = total_ht, total_tva, total_ttc
    invoice.invoice_number = _find_invoice_number(rows, header_index)
    invoice.invoice_date = _find_date(rows, page_height)
    invoice.supplier_ice = _find_ice(rows)

    item_sum = sum((line.amount for line in invoice.lines), Decimal("0.00"))
    paper_base = item_sum + invoice.carried_amount
    if total_ht is not None and amount_field == "amount":
        if abs(paper_base - total_ht) > max(Decimal("0.05"), abs(total_ht) * Decimal("0.002")):
            invoice.warnings.append(f"Lines total {paper_base} but the paper shows Total HT {total_ht}.")

    if not invoice.invoice_number:
        invoice.warnings.append("Invoice number not found; type it before saving.")
    if invoice.invoice_date is None:
        invoice.warnings.append("Invoice date not found; pick it before saving.")

    for field_name, bounds in list(column_bounds.items()):
        invoice.columns[field_name] = (bounds[0] / page_width, bounds[1] / page_width)
    for field_name, bounds in (("reference", reference_bounds), ("label", label_bounds)):
        if bounds:
            invoice.columns[field_name] = (bounds[0] / page_width, bounds[1] / page_width)
    if ignore_ranges:
        left = min(left for left, _ in ignore_ranges)
        right = max(right for _, right in ignore_ranges)
        invoice.columns["ignore"] = (left / page_width, right / page_width)

    return invoice
