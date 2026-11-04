# TAJ FROID ERP

Desktop ERP for TAJ FROID: inventory, CRM, suppliers, purchasing, sales,
finance, checks and deposits, audit trail, and Moroccan facture PDFs.

The application is a PySide6 desktop client backed by a local SQLite
database. It is designed for a single shop workstation and keeps all
business rules in the service layer.

## Architecture

```
UI (PySide6 widgets/dialogs)
        │
        ▼
Service layer (permissions, validation, audit, transactions)
        │
        ▼
SQLAlchemy ORM → SQLite (WAL, foreign keys, Alembic migrations)
```

- The **service layer is the security boundary**. Hiding a button in the
  UI is convenience only; every write re-checks the caller's
  `RequestContext` permission.
- Money is stored as `Decimal` / SQLite `NUMERIC`, never as `float`.
- Multi-step writes use the `@transactional` decorator.
- Alembic is the only supported way to change the schema.
- Audit events are append-only and are written by SQLAlchemy listeners.

## Requirements

- Windows 10/11 (the packaging and installer pipeline targets x64).
- Python **3.12 or newer**.
- A writable user profile. Runtime data lives under
  `%LOCALAPPDATA%\TAJ_FROID`, not in the repository.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the application from the repository root:

```powershell
python main.py
```

The first start runs health checks, applies Alembic migrations, creates
the built-in roles/permissions, and opens the mandatory first-run setup
dialog. The bootstrap account is `admin` with the factory password
`admin`; the setup dialog forces a new username and a strong password
before the main window can open. Do not deploy an installation that has
not completed this step.

## Configuration

Configuration is read from environment variables and an optional `.env`
file in the repository root. `.env` files are git-ignored.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TAJ_ENVIRONMENT` | `development` (`production` in a frozen build) | Logging verbosity and redaction mode. |
| `TAJ_TRANSLATIONS_DIR` | `resources/translations` | Override the translation catalog (used by tests). |
| `DATABASE_URL` | SQLite under `%LOCALAPPDATA%` | Used by the API prototype only; the desktop app uses `src/core/paths.py`. |
| `SECRET_KEY` | development placeholder | JWT signing key for the optional API prototype. Must be changed before any API use. |

Production logging:

- no console handler;
- file handler at `WARNING`;
- `backtrace`/`diagnose` disabled;
- passwords, tokens, API keys and Argon2 hashes are redacted before the
  record reaches disk.

A packaged build defaults to production even when no `.env` file is
shipped. Set `TAJ_ENVIRONMENT=development` only for local debugging.

## Data locations

| Data | Location |
| --- | --- |
| Database | `%LOCALAPPDATA%\TAJ_FROID\data\taj_froid.db` |
| Backups | `%LOCALAPPDATA%\TAJ_FROID\backups` |
| Logs | `%LOCALAPPDATA%\TAJ_FROID\logs\app.log` |
| Config | `%LOCALAPPDATA%\TAJ_FROID\config` |
| Temp scratch | `%LOCALAPPDATA%\TAJ_FROID\temp` |
| Website sync | `%LOCALAPPDATA%\TAJ_FROID\website_sync` (configurable) |

Uninstalling the application deliberately does **not** delete this tree.
Database, backups and logs survive upgrades and uninstalls.

## Roles and permissions

Built-in roles are reconciled on every start:

- **Administrator** — the `.*` superuser grant.
- **Manager** — inventory, CRM, suppliers, sales and purchasing.
- **Employee** — view products/customers and create sales invoices.

Permissions added in a later release are inserted into an existing
database and granted to the matching built-in role. Existing custom
grants are never removed. The complete catalog lives in
`src/modules/authentication/bootstrap.py`.

User management, backup/restore, diagnostics, VACUUM and system
preferences require `Settings.System.Update` or the relevant
`Security.Users.*` permission. The UI hides those sections when the
signed-in user lacks the permission, and the service rejects the call
even if the UI is bypassed.

## Backup and restore

- A backup is a zip containing a consistent SQLite snapshot
  (`taj_froid.db`), created through SQLite's backup API.
- A pre-migration backup is taken automatically before Alembic runs.
- A best-effort safety backup is taken before a restore; a corrupt or
  locked live database does not block recovery from a validated backup.
- Backups are verified (zip integrity + SQLite header + SQLite
  integrity check) before the live database is replaced.
- Retention is controlled by `backup.retention.count` (default 15).
- The shutdown hook creates a `shutdown` backup.

Restore from **Settings → Backup & Recovery**. External restore files are
accepted, but must be a real zip containing a healthy `taj_froid.db`.
The application closes after a successful restore so the next start opens
the restored database.

## Website sync

The ERP can export `website_catalog.json` to a configured folder and
import `price_updates.json` dropped by the website. The folder can only
be changed by a user with `Settings.WebsiteSync.Export`; importing
requires `Settings.WebsiteSync.Import`.

See [docs/WEBSITE_SYNC.md](docs/WEBSITE_SYNC.md) for the file contract
and [docs/CHECKS_AND_DEPOSITS.md](docs/CHECKS_AND_DEPOSITS.md) for the
check/deposit rules.

## Tests and checks

```powershell
python -m pytest -q
python -m compileall -q src main.py tests
git diff --check
```

Pytest cache and temporary trees are kept inside the repository
(`.pytest_cache_local`, `.pytest_tmp`) because the shared Windows `%TEMP%`
folder can be ACL-locked on shop PCs.

The suite covers services, permissions, transactions, audit
immutability, backups, migrations, check/deposit flows, returns, logging
redaction and UI layout/localization guards. It does not replace a manual
PySide6 smoke test on a real workstation.

## Build and installer

```powershell
.\build.bat
```

The pipeline installs `requirements-dev.txt`, generates a PyInstaller
spec, and produces `dist\TAJ_FROID_ERP\TAJ_FROID_ERP.exe`. The spec bundles
`alembic.ini`, `migrations/` and `resources/translations/`, and excludes
the experimental API, WebSocket helper and tests.

Build the installer with Inno Setup:

```text
installer\taj_froid.iss
```

The installer requires administrator rights for installation but stores
all user data under the user's `%LOCALAPPDATA%` profile.

## Experimental API

`src/api` is an **unwired prototype**. It is not started by `main.py`, is
excluded from packaging, and requires the optional `api` extra plus an
explicit `TAJ_ENABLE_EXPERIMENTAL_API=1` opt-in. It is not covered by the
desktop security model and must not be exposed on a network without a
separate review. See [src/api/README.md](src/api/README.md).

## Troubleshooting

**The app exits at startup after a migration failure.**
Use the recovery dialog to restore the automatic pre-migration backup.
The app closes after the restore so the old schema is never opened by the
new binary; restart it, or install the matching release. Do not delete the
database without taking a copy first.

**“Database is locked”.**
Close other copies of the application and any SQLite browser that has the
database open. The engine uses WAL and a 5-second busy timeout.

**Backups fail with a permission error.**
Check that `%LOCALAPPDATA%\TAJ_FROID\backups` and `...\temp` are writable
by the signed-in Windows user. The app intentionally keeps scratch files
inside this tree rather than `%TEMP%`.

**The UI shows translation keys instead of text.**
Confirm `resources/translations/en` and `.../fr` exist. A packaged build
must include them; the PyInstaller spec does this by default.

**I forgot the administrator password.**
There is no password-recovery backdoor. Restore a backup, or use another
administrator account to reset it from Settings → User Management.

## Repository layout

```text
main.py                  desktop entry point
src/
  core/                  config, paths, logging, backup, migrations, health
  database/              engine, session, transaction, audit listener
  modules/               authentication, inventory, CRM, suppliers,
                         purchasing, sales, finance, reports, settings,
                         pricing, websync, audit
  security/              RBAC and sanitizers
  ui/                    PySide6 windows, widgets, dialogs, models
  api/                   experimental prototype (not shipped)
tests/                   pytest suite
migrations/              Alembic revisions
docs/                    operational documentation
engineering/             historical plans, reviews and task records
```

## Security notes

- Passwords are Argon2id hashes; repeated failures trigger a growing
  temporary lockout.
- The factory administrator password is usable only long enough for the
  mandatory first-run setup; the setup path is replay-safe.
- Restores are permission-gated, confirmation-gated, and validate the
  archive before replacing the live database.
- Audit events reject ORM updates/deletes. Do not use bulk SQL against the
  audit table.
- See [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for the adversarial review
  and the status of each finding.
