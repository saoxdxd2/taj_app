# Experimental API (not shipped)

This directory is an **unwired prototype**. It is not started by
`main.py`, it is excluded from the desktop package and from the
PyInstaller build, and its dependencies are only installed through the
optional `api` extra:

```powershell
pip install -e ".[api]"
$env:TAJ_ENABLE_EXPERIMENTAL_API = "1"
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Do not expose it on a network or treat it as production code. The desktop
application uses the service layer directly; this prototype has not been
through the same security review, its schemas do not match the current
ORM models, and it does not use the desktop `RequestContext` / RBAC
boundary.

The legacy router and WebSocket hardening tests remain in
`tests/unit/security/test_api_hardening.py` so the old vulnerabilities
cannot silently return if the prototype is revived.
