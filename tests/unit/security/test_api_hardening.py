"""
Regression tests for the vulnerabilities found in the adversarial audit.

These exist so the same holes cannot be reopened. They assert on the
source, because the API modules cannot be imported in the test environment
(pydantic_settings is absent) - and a source-level assertion is what
catches the regression anyway.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
API = ROOT / "src" / "api"
ROUTES = API / "routes.py"
MAIN = API / "main.py"
REGISTER = API / "v1" / "endpoints" / "auth.py"
SETTINGS = API / "core" / "settings.py"
DIAGNOSTICS = ROOT / "src" / "core" / "diagnostics.py"


def _route_decorators(text):
    """Yields (decorator_line, following_signature) for each route."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "@router." in line:
            yield line.strip(), "\n".join(lines[i: i + 10])


# --- 1. No unauthenticated endpoints in the legacy router ----------------

def test_every_get_endpoint_requires_a_token():
    """
    Regression: routes.py was mounted with no auth at all, so anyone who
    could reach the port could read the catalog, sales and analytics.
    """
    offenders = []
    for decorator, signature in _route_decorators(ROUTES.read_text(encoding="utf-8")):
        if not decorator.startswith("@router.get"):
            continue
        if "Depends(get_current_user)" not in signature:
            offenders.append(decorator)
    assert not offenders, f"unauthenticated GET endpoints: {offenders}"


def test_every_write_endpoint_requires_admin():
    """
    Regression: POST /products and PUT /products/{id} accepted anonymous
    writes, allowing the whole catalog to be overwritten.

    POST /sales is the documented exception: a cashier must be able to
    record a sale, so it requires a valid token rather than admin.
    """
    admin_only = {"admin"}
    authenticated = {"/sales"}
    offenders = []
    for decorator, signature in _route_decorators(ROUTES.read_text(encoding="utf-8")):
        if not re.match(r"@router\.(post|put|patch|delete)", decorator):
            continue
        if "Depends(require_admin())" in signature:
            continue
        if "Depends(get_current_user)" in signature:
            # Permitted only for the explicitly listed non-admin writes.
            if not any(name in decorator for name in authenticated):
                offenders.append(f"{decorator} (should be admin-only)")
            continue
        offenders.append(f"{decorator} (no auth at all)")
    assert not offenders, f"write endpoints not gated: {offenders}"


def test_router_imports_the_auth_dependencies():
    text = ROUTES.read_text(encoding="utf-8")
    assert "from src.api.core.security import" in text
    assert "get_current_user" in text


def test_websocket_requires_a_token():
    """
    Regression: the socket broadcast live inventory and sales to anyone
    who connected.
    """
    text = ROUTES.read_text(encoding="utf-8")
    socket_section = text.split("@router.websocket", 1)[1][:900]
    assert "decode_token" in socket_section, (
        "websocket must validate a token before accepting the connection"
    )


# --- 2. No self-assigned roles on public registration --------------------

def test_register_does_not_trust_request_roles():
    """
    Regression: /register iterated the roles from the request body and
    created any role it did not know, so an anonymous caller could
    self-assign Administrator.
    """
    text = REGISTER.read_text(encoding="utf-8")
    assert "for role_name in user_data.roles" not in text, (
        "register still assigns roles straight from the request body"
    )
    assert "public_registration_roles" in text, (
        "register must filter roles through the allow-list"
    )


def test_privileged_roles_are_rejected_by_configuration():
    """
    The allow-list itself must refuse privileged roles, otherwise a
    misconfiguration re-opens the escalation.
    """
    text = SETTINGS.read_text(encoding="utf-8")
    assert "public_registration_roles" in text
    for forbidden in ("admin", "manager", "superuser", "root"):
        assert forbidden in text, (
            f"'{forbidden}' must be in the forbidden-role set"
        )


# --- 3. CORS ------------------------------------------------------------

def test_cors_is_not_wildcard_with_credentials():
    """
    Regression: allow_origins=["*"] together with allow_credentials=True
    let any website reuse a logged-in user's session.
    """
    # Comments document the old value, so only real code is inspected.
    code = "\n".join(
        line for line in MAIN.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )
    assert 'allow_origins=["*"]' not in code, "hardcoded wildcard CORS origin"
    assert "allow_credentials=True" not in code, (
        "credentials must be derived, not unconditionally enabled"
    )
    assert "_allow_credentials" in code
    # Production must fail closed rather than fall back to '*'.
    assert "_is_production" in code
    assert "RuntimeError" in code


# --- 4. SQL identifier quoting ------------------------------------------

def test_table_names_are_quoted_in_diagnostics():
    """
    Regression: the diagnostics bundle interpolated a table name straight
    into SQL. Table names cannot be parameterised, so a name containing a
    quote could inject SQL.
    """
    text = DIAGNOSTICS.read_text(encoding="utf-8")
    assert 'cursor.execute(f"SELECT count(*) FROM {table_name}")' not in text, (
        "unquoted table identifier in SQL"
    )
    assert "replace('\"', '\"\"')" in text, (
        "table identifier must be quoted with double-quote doubling"
    )


def test_no_unquoted_sql_fstrings_anywhere():
    """
    Broader sweep: no execute() call may build SQL from an f-string that
    interpolates a bare identifier.
    """
    offenders = []
    pattern = re.compile(r"execute\(\s*f['\"]", re.IGNORECASE)
    for path in (ROOT / "src").rglob("*.py"):
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if pattern.search(line):
                if "quoted" in line:
                    continue
                offenders.append(f"{path.name}:{i}: {stripped[:70]}")
    assert not offenders, "unquoted SQL f-strings:\n" + "\n".join(offenders)


# --- 5. No dynamic code execution ---------------------------------------

def test_no_eval_or_pickle():
    """
    Sweep for arbitrary code execution primitives. `dialog.exec()` is a Qt
    call and is not Python's exec, so it is not flagged.
    """
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        for i, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for token in ("eval(", "pickle.loads", "os.system(",
                          "shell=True", "yaml.load("):
                if token in stripped:
                    offenders.append(f"{path.name}:{i}: {token}")
    assert not offenders, f"code-execution primitives: {offenders}"
