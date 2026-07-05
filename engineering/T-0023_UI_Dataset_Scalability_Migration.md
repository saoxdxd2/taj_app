# Engineering Decision Record: T-0023 - UI Dataset Scalability Migration

## Context
The application relied on `QTableWidget` to render datasets across the CRM, Inventory, Purchasing, Suppliers, and Sales modules. `QTableWidget` creates a distinct QWidget wrapper for every single cell. For large datasets (e.g., 10,000 products), this instantiates 70,000 UI elements, causing extreme memory consumption and severe UI blocking during refreshes.

## Decision
We migrated all core data tables to Qt's Model/View architecture, specifically pairing `QTableView` with subclasses of `QAbstractTableModel`.

To maximize code reuse without sacrificing domain separation, we established a Model/View hierarchy:
- `BaseTableModel`: Encapsulates reusable Qt boilerplate (`rowCount`, `columnCount`, `headerData`, `flags`, and `update_data`).
- **Entity Models**: `CustomerTableModel`, `SupplierTableModel`, `ProductTableModel`, `PurchaseTableModel`, `PurchaseItemTableModel`, `InvoiceTableModel`, `InvoiceItemTableModel`.

These entity models are completely lightweight, containing only the column definitions and the entity-specific attribute mapping within the `data()` method.

## Consequences
- **Positive:** The UI can now render tens of thousands of rows concurrently without locking the main thread.
- **Positive:** Memory footprint drastically reduced.
- **Positive:** Separation of concerns is respected. The UI layer delegates entirely to the Model, which safely extracts domain data.
- **Optimization Target:** `update_data()` currently utilizes `beginResetModel()` and `endResetModel()`. If real-time sorting or scrolling while refreshing becomes necessary, this can be optimized to differential updates (`insertRows`, `removeRows`) in the future without changing the UI components.
