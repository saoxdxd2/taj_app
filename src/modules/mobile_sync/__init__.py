"""Mobile sync agent: bridges the Taj-Froid desktop ERP with the mobile PWA relay.

The desktop remains the only place that OCRs, reviews and posts supplier
invoices. This package only moves encrypted bytes and status events; it
never performs a financial write on its own.
"""