import os
from datetime import datetime
from loguru import logger
from src.core.paths import BACKUP_DIR  # or use desktop path
from typing import Dict, List

# Graceful degradation check
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("ReportLab is not installed. PDF generation will be disabled.")

class PDFEngine:
    @staticmethod
    def is_available() -> bool:
        return PDF_AVAILABLE

    @staticmethod
    def generate_invoice_pdf(invoice_data: Dict, items: List[Dict]) -> str:
        """
        Generates a PDF for an invoice.
        Raises an exception if PDF_AVAILABLE is False.
        """
        if not PDF_AVAILABLE:
            raise RuntimeError("PDF engine (ReportLab) is unavailable.")
            
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop_path) or not os.path.isdir(desktop_path):
            desktop_path = os.path.expanduser("~") # Fallback to user home
            
        filename = f"Invoice_{invoice_data.get('invoice_number', 'unknown')}.pdf"
        filepath = os.path.join(desktop_path, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Header
        elements.append(Paragraph(f"<b>INVOICE: {invoice_data.get('invoice_number', '')}</b>", styles['Heading1']))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Paragraph(f"Customer ID: {invoice_data.get('customer_id', '')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Table Data
        from decimal import Decimal
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
            
        # Empty row and Total
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
