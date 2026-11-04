# Security Audit — Adversarial Pass

Scope: `src/`, performed by attempting the attacks rather than by reading
for patterns. Findings are ordered by severity.

> **Current status:** every finding below has a fix applied. The FastAPI
> prototype in `src/api` is excluded from the desktop package, is not
> started by `main.py`, and refuses to import without an explicit
> `TAJ_ENABLE_EXPERIMENTAL_API=1` opt-in. Re-run this audit before
> treating that prototype as a production service.

## CRITICAL

### 1. Unauthenticated write access to the product catalog
**File:** `src/api/routes.py` (mounted at `/api/v1` in `src/api/main.py:128`)

`POST /api/v1/products` and `PUT /api/v1/products/{id}` have **no
authentication dependency**. The v1 endpoint files
(`src/api/v1/endpoints/products.py` etc.) do require a token, but
`routes.py` is a second, older router that is still mounted.

Attack: `curl -X POST /api/v1/products -d '{"name":"pwned","sku":"X","sale_price":"1.00"}'`
succeeds with no credentials. An attacker on the network can rewrite the
entire catalog and its prices.

The same router exposes unauthenticated `GET /products`, `GET /sales` and
`GET /analytics/dashboard`, leaking revenue figures.

**Impact:** total loss of data integrity and confidentiality for the
catalog and sales data.
**Fix applied:** all `routes.py` endpoints now require a bearer token.

### 2. Unauthenticated self-registration with arbitrary roles
**File:** `src/api/v1/endpoints/auth.py:24-70`

`POST /register` is public and takes `user_data.roles` **from the request
body**. There is no allow-list: the handler looks up each requested role
and **creates it if it does not exist** (lines 49-51).

Attack: `POST /register {"username":"a","password":"x","roles":["Administrator"]}`
creates an Administrator account. Even for an existing role, self-granting
it is privilege escalation.

**Impact:** complete authentication bypass → administrator access.
**Fix applied:** the endpoint is restricted to the default least-privilege
role and role assignment now requires an existing administrator token.

### 3. CORS allows every origin together with credentials
**File:** `src/api/main.py:58-64`

```python
allow_origins=["*"], allow_credentials=True
```

Browsers reject that combination, but frameworks and non-browser clients
honour it, and it removes the last cross-origin barrier.

**Impact:** any website visited by a logged-in user can call the API with
their session.
**Fix applied:** origins come from settings; `*` is only allowed outside
production and never together with credentials.

## HIGH

### 4. SQL identifier injection in diagnostics
**File:** `src/core/diagnostics.py:56`

```python
cursor.execute(f"SELECT count(*) FROM {table_name}")
```

Table names cannot be parameterised, so the identifier was interpolated
unquoted. A table named `a"; DROP TABLE user; --` executes.

**Fix applied:** identifier is quoted with `"` doubling, which is the only
safe form for a non-bindable identifier.

## MEDIUM

### 5. WebSocket endpoint unauthenticated
**File:** `src/api/routes.py` — `@router.websocket("/ws/{client_type}")`
used to accept a connection without a token, so anyone could subscribe
to live inventory and sales broadcasts.

**Fix applied:** the socket validates a bearer token before `accept()`
and closes with `WS_1008_POLICY_VIOLATION` otherwise. The whole `src/api`
prototype is also now excluded from the desktop package and refuses to
import unless `TAJ_ENABLE_EXPERIMENTAL_API=1` is explicitly set.

### 6. Unvalidated restore path from the UI
**File:** `src/ui/widgets/settings_widget.py` — a file chosen with
`QFileDialog` used to be passed to `BackupManager.restore_backup` with no
validation.

**Fix applied:** the UI passes the absolute path returned by
`SystemService.list_backups` instead of rebuilding it from a filename,
which closes the path-traversal gap. `BackupManager` also rejects
non-zip files, symlinks, archives without `taj_froid.db`, files whose
contents are not a SQLite database, and databases that fail
`PRAGMA integrity_check`. A safety backup is taken before the live
database is replaced.

## Notes on what was checked and found clean

- No `eval`, `exec`, `pickle`, `yaml.load`, or `os.system` anywhere.
  (The `dialog.exec()` hits are Qt, not Python's `exec`.)
- All service-layer write methods carry a `PermissionManager` check.
- The desktop login path redacts usernames from the log and locks out
  after repeated failures.
- No plaintext secrets; passwords are Argon2id.
- Backup restore is confirmation-gated in the UI.
