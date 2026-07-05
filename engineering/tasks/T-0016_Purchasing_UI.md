# Task Manifest

Task ID: T-0016

Title: Purchasing UI

Status: Closed

---

Business Objective

Provide a user interface for the Procurement team to create draft purchases, add line items from the inventory, and validate purchase orders to trigger stock and financial updates.

---

Engineering Objective

- Implement `PurchaseWidget` containing a split-view table for Purchase Orders and Purchase Items.
- Implement `NewPurchaseDialog` for creating a draft purchase tied to a supplier.
- Implement `PurchaseAddItemDialog` for associating products, quantities, and unit costs to a draft purchase.
- Inject the mock `RequestContext` representing the administrator to interact with the hardened Enterprise services.

---

Business Capability Added

Users can now:
- ✓ View all historical and draft purchases.
- ✓ Create new draft purchases tied to active suppliers.
- ✓ Add products to draft purchases with precise quantity and unit cost.
- ✓ Validate purchases, updating inventory stock levels and generating financial liabilities automatically.

---

Validation

- ✓ GUI connected to Enterprise backend
- ✓ Context injected properly mimicking Administration role.
- ✓ Split-view properly displays Line Items related to the selected Purchase Order.
- ✓ Validation enforces Draft state requirements before processing financial transactions.

---

Performance

- Loading complexity: O(n) rendering of the QTableWidget for Purchase list.
- Lazy-loading implemented for Purchase Items (items are only fetched and rendered when a Purchase is selected).
- Memory impact: PySide6 model handles widget lifecycle independently.

---

Authorization

- Hardcoded `RequestContext` passes `Administrator` Role.
- Bypasses PermissionManager using wildcard `.*`.

---

Audit

- `CREATE_PURCHASE` ✓
- `ADD_PURCHASE_ITEM` ✓
- `VALIDATE_PURCHASE` ✓

---

Deliverables

- `src/ui/dialogs/purchase_dialogs.py`
- `src/ui/widgets/purchase_widget.py`

---

Notes

This UI integrates directly with the hardened services built in T-0015. Next step is Sales UI and then the Main Navigation Shell.
