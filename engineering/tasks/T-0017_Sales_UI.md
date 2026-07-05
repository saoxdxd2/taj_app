# Task Manifest

Task ID: T-0017

Title: Sales UI

Status: Closed

---

Business Objective

Provide a user interface for the Sales team to create draft invoices, assign products as line items, and validate invoices to decrement stock levels and record incoming revenue.

---

Engineering Objective

- Implement `SalesWidget` containing a split-view table for Invoices and Invoice Items.
- Implement `NewInvoiceDialog` for creating draft invoices linked to a CRM Customer.
- Implement `InvoiceAddItemDialog` for associating products, quantities, unit prices, and VAT rates.
- Inject the mock `RequestContext` simulating an Administrator to seamlessly interoperate with the Enterprise layer constraints.

---

Business Capability Added

Users can now:
- ✓ View all historical and draft invoices.
- ✓ Create new draft invoices tied to active CRM customers.
- ✓ Add products to invoices with pre-filled default pricing and VAT rates.
- ✓ Validate invoices to atomically deduct inventory and register financial incoming entries.

---

Validation

- ✓ GUI connected to Enterprise backend
- ✓ Context injected properly mimicking Administration role.
- ✓ Split-view properly displays Line Items related to the selected Invoice.
- ✓ Validation enforces Draft state requirements and intercepts atomic transaction failures (e.g., Insufficient Stock).

---

Performance

- Loading complexity: O(n) rendering of the QTableWidget for Invoice list.
- Lazy-loading implemented for Invoice Items.
- Memory impact: PySide6 model handles widget lifecycle independently.

---

Authorization

- Hardcoded `RequestContext` passes `Administrator` Role.
- Bypasses PermissionManager using wildcard `.*`.

---

Audit

- `CREATE_INVOICE` ✓
- `ADD_INVOICE_ITEM` ✓
- `VALIDATE_INVOICE` ✓

---

Deliverables

- `src/ui/dialogs/sales_dialogs.py`
- `src/ui/widgets/sales_widget.py`

---

Notes

The UI architecture identically mirrors Purchasing, maintaining consistent interaction paradigms across the ERP.
