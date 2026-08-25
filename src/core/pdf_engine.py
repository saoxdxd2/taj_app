import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from loguru import logger

# Graceful degradation check
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("ReportLab is not installed. PDF generation will be disabled.")

if PDF_AVAILABLE:
    DARK = colors.HexColor("#1f3a5f")
    LIGHT = colors.HexColor("#eef2f7")
else:
    DARK = LIGHT = None  # never used when the engine is unavailable


class PDFEngine:
    @staticmethod
    def is_available() -> bool:
        return PDF_AVAILABLE

    # ------------------------------------------------------------------
    # Facture (Moroccan invoice layout)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_facture_pdf(invoice_data: Dict,
                             items: List[Dict],
                             customer_data: Optional[Dict] = None,
                             company_data: Optional[Dict] = None,
                             output_dir: Optional[str] = None) -> str:
        """
        Generates a facture PDF matching the classic Moroccan layout:
        - Header: seller identity (ICE/RC/IF/Patente) + FACTURE N° + date
        - Client block
        - Line items with HT amounts and VAT
        - Totals: Total HT, Total TVA, Total TTC (DH)
        - Footer note + bank details

        items dicts: {description, quantity, unit_price, vat_rate}
        Returns the path of the written file.
        """
        if not PDF_AVAILABLE:
            raise RuntimeError("PDF engine (ReportLab) is unavailable.")

        customer_data = customer_data or {}
        company_data = company_data or {}

        if output_dir is None:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop_path) or not os.path.isdir(desktop_path):
                desktop_path = os.path.expanduser("~")
            output_dir = desktop_path

        number = str(invoice_data.get("invoice_number", "unknown"))
        filepath = os.path.join(output_dir, f"Facture_{number.replace('/', '-')}.pdf")

        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()
        style_right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
        elements = []

        # --- Header: seller identity | FACTURE title ---
        def _line(label, value):
            value = (value or "").strip()
            return f"{label}: <b>{value}</b>" if value else ""

        company_lines = [
            f"<b><font size=14>{company_data.get('company_name', 'TAJ FROID')}</font></b>",
        ]
        for label, key in (("ICE", "ice_number"), ("RC", "rc_number"),
                           ("IF", "if_number"), ("Patente", "patente_number")):
            text = _line(label, company_data.get(key))
            if text:
                company_lines.append(text)
        address_parts = [p for p in (
            company_data.get("address_street"), company_data.get("address_city")
        ) if p]
        if address_parts:
            company_lines.append(" - ".join(address_parts))
        contact_parts = [p for p in (
            company_data.get("phone"), company_data.get("email")
        ) if p]
        if contact_parts:
            company_lines.append(" | ".join(contact_parts))

        date_str = invoice_data.get("date") or datetime.now().strftime("%d/%m/%Y")
        header_right = [
            Paragraph("<b><font size=18>FACTURE</font></b>", style_right),
            Paragraph(f"N° <b>{number}</b>", style_right),
            Paragraph(f"Date : {date_str}", style_right),
        ]

        header_table = Table(
            [[Paragraph("<br/>".join(company_lines), styles["Normal"]), header_right]],
            colWidths=[110 * mm, 70 * mm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, 0), 1, DARK),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 8 * mm))

        # --- Client block ---
        client_lines = ["<b>Client</b>"]
        client_name = customer_data.get("company_name") or f"Client #{invoice_data.get('customer_id', '?')}"
        client_lines.append(f"<b>{client_name}</b>")
        ice = (customer_data.get("ice_number") or "").strip()
        if ice:
            client_lines.append(f"ICE : {ice}")
        client_address = [p for p in (
            customer_data.get("address_street"), customer_data.get("address_city")
        ) if p]
        if client_address:
            client_lines.append(" - ".join(client_address))
        client_phone = (customer_data.get("phone") or "").strip()
        if client_phone:
            client_lines.append(f"Tél : {client_phone}")

        client_table = Table([[Paragraph("<br/>".join(client_lines), styles["Normal"])]],
                             colWidths=[90 * mm])
        client_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.grey),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(client_table)
        elements.append(Spacer(1, 6 * mm))

        # --- Items table ---
        data = [["Désignation", "Qté", "P.U. HT", "TVA %", "Montant HT"]]
        total_ht = Decimal("0.00")
        vat_by_rate: Dict[Decimal, Decimal] = {}

        for item in items:
            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("unit_price", 0)))
            vat_rate = Decimal(str(item.get("vat_rate", 0)))
            description = str(item.get("description") or item.get("product_id", ""))
            line_ht = qty * price
            line_vat = line_ht * vat_rate / Decimal("100")
            total_ht += line_ht
            vat_by_rate[vat_rate] = vat_by_rate.get(vat_rate, Decimal("0.00")) + line_vat

            data.append([
                description[:80],
                str(qty),
                f"{price:,.2f}",
                f"{vat_rate:g}%",
                f"{line_ht:,.2f}",
            ])

        total_tva = sum(vat_by_rate.values(), Decimal("0.00"))
        total_ttc = total_ht + total_tva

        items_table = Table(data, colWidths=[85 * mm, 18 * mm, 28 * mm, 19 * mm, 30 * mm])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 5 * mm))

        # --- Totals block (right aligned) ---
        totals_rows = [["Total HT", f"{total_ht:,.2f} DH"]]
        for rate in sorted(vat_by_rate):
            totals_rows.append([f"TVA {rate:g}%", f"{vat_by_rate[rate]:,.2f} DH"])
        totals_rows.append(["Total TTC", f"{total_ttc:,.2f} DH"])

        totals_table = Table(totals_rows, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
        last_row = len(totals_rows) - 1
        totals_table.setStyle(TableStyle([
            ("FONTNAME", (0, last_row), (-1, last_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, last_row), (-1, last_row), DARK),
            ("TEXTCOLOR", (0, last_row), (-1, last_row), colors.white),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(totals_table)

        # --- Footer ---
        footer_note = company_data.get("invoice_footer_note")
        if footer_note:
            elements.append(Spacer(1, 10 * mm))
            elements.append(Paragraph(str(footer_note), styles["Italic"]))
        rib = (company_data.get("bank_rib") or "").strip()
        bank = (company_data.get("bank_name") or "").strip()
        if rib or bank:
            elements.append(Paragraph(
                f"Coordonnées bancaires : {bank}{' - RIB : ' + rib if rib else ''}",
                styles["Normal"],
            ))

        try:
            doc.build(elements)
        except Exception as e:
            raise RuntimeError(f"Failed to write PDF to {filepath}: {e}")

        logger.info(f"Generated facture PDF: {filepath}")
        return filepath

    # ------------------------------------------------------------------
    # Legacy simple invoice export (kept for compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_invoice_pdf(invoice_data: Dict, items: List[Dict]) -> str:
        """Legacy minimal invoice export."""
        if not PDF_AVAILABLE:
            raise RuntimeError("PDF engine (ReportLab) is unavailable.")

        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_path) or not os.path.isdir(desktop_path):
            desktop_path = os.path.expanduser("~")

        filename = f"Invoice_{invoice_data.get('invoice_number', 'unknown')}.pdf"
        filepath = os.path.join(desktop_path, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph(f"<b>INVOICE: {invoice_data.get('invoice_number', '')}</b>", styles['Heading1']))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Paragraph(f"Customer ID: {invoice_data.get('customer_id', '')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        data = [['Product ID', 'Quantity', 'Unit Price', 'VAT Rate', 'Total']]
        for item in items:
            qty = Decimal(str(item.get('quantity', 0)))
            price = Decimal(str(item.get('unit_price', 0)))
            vat = Decimal(str(item.get('vat_rate', 0)))
            total = (qty * price) * (Decimal("1") + (vat / Decimal("100")))
            data.append([
                str(item.get('product_id', '')),
                str(qty),
                f"{price:.2f}",
                f"{vat}%",
                f"{total:.2f}"
            ])

        grand_total = Decimal(str(invoice_data.get('total_amount', 0)))
        data.append(['', '', '', 'Grand Total:', f"{grand_total:.2f}"])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)

        try:
            doc.build(elements)
        except Exception as e:
            raise RuntimeError(f"Failed to write PDF to {filepath}: {e}")

        logger.info(f"Generated PDF invoice: {filepath}")
        return filepath