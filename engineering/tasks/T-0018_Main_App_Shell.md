# Task Manifest

Task ID: T-0018

Title: Main Application Shell & Authentication

Status: Closed

---

Business Objective

Provide a unified, secure entry point for all enterprise operations. Remove development mock environments and enforce cryptographic authentication (Argon2id) prior to granting access to business widgets.

---

Engineering Objective

- Implement `CurrentSession` singleton to globally manage the active user's `RequestContext`.
- Implement `AuthenticationService` to hash and verify passwords, and authenticate the `User` models against the database.
- Strip all mock `RequestContext` injections from `ProductWidget`, `CustomerWidget`, `SupplierWidget`, `PurchaseWidget`, and `SalesWidget`, instructing them to dynamically pull their context via `CurrentSession.get_context()`.
- Implement `LoginDialog` mapping user credentials to `AuthenticationService`.
- Implement `MainWindow` deploying a `QStackedWidget` navigation shell to route users between the distinct domain widgets.
- Write a unified entry point `main.py` that bootstraps the SQLite database and launches the Login Gateway.

---

Business Capability Added

Users can now:
- ✓ Authenticate securely using their credentials.
- ✓ Access all ERP modules from a single unified desktop window.
- ✓ Rely on proper Role-Based Access Control automatically mapped from their login profile.

---

Validation

- ✓ Authentication service rejects invalid passwords.
- ✓ Database schemas initialize successfully on a fresh launch.
- ✓ Widgets correctly pull their execution context without crashing.
- ✓ Navigation sidebar correctly switches the StackedWidget pages.

---

Performance

- Loading complexity: Near-instantaneous O(1) context retrieval.
- Memory impact: Re-uses instances of the 5 main domain widgets within the StackedWidget, retaining their data until refreshed.

---

Authorization

- Roles correctly parse to explicit permissions upon login.
- Administrator gets `.*` wildcard. Manager gets broad `.*` domain rights. Employee gets read-only/create constraints.

---

Audit

- Authentication failures and success are logged.
- The `CurrentSession` ensures the user's explicit ID is attached to all generated audit logs from downstream widgets.

---

Deliverables

- `src/core/session.py`
- `src/modules/authentication/services.py`
- `src/ui/main_window.py`
- `main.py`
- Refactored all `src/ui/widgets/*.py`

---

Notes

The transition from development mock to full enterprise session state is complete. The system is now technically ready for a full demonstration or build sequence.
