"""HTTP client for the mobile relay.

Uses httpx. All secrets are read from the credential store, never from
the database or logs. The client never logs request/response bodies
(which may contain ciphertext or tokens).

Every JSON response goes through one bounded, log-safe decoder: HTML, empty
bodies, invalid JSON and oversized payloads raise :class:`RelayResponseError`
with a generic message instead of leaking response content into logs.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from .crypto import load_agent_token
from .sync import RelayResponseError, SyncConfigError, safe_text

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SCAN_ITEMS = 1000


def _decode_body(body: bytes, headers: Any, allow_empty: bool = False) -> Any:
    if not body:
        if allow_empty:
            return {}
        raise RelayResponseError("Relay returned an empty response.")
    if len(body) > MAX_RESPONSE_BYTES:
        raise RelayResponseError("Relay response is too large.")

    content_type = ""
    try:
        content_type = safe_text(headers.get("content-type", ""), 120).lower()
    except Exception:  # noqa: BLE001 - hostile response headers
        pass
    if body.lstrip()[:1] == b"<" or "html" in content_type:
        raise RelayResponseError("Relay returned non-JSON content.")

    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RelayResponseError("Relay returned invalid JSON.") from exc


def _scan_path_id(scan_id: Any) -> str:
    """URL-quote a relay ID before embedding it in a request path."""
    if not isinstance(scan_id, str) or not scan_id.strip():
        raise RelayResponseError("Invalid relay scan ID.")
    return quote(scan_id.strip(), safe="")


class RelayClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = str(base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self, authenticated: bool = True) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if authenticated:
            token = self._token if self._token is not None else load_agent_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # ---- shared request helpers ----

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        authenticated: bool = True,
        allow_empty: bool = False,
    ) -> Any:
        kwargs: Dict[str, Any] = {"headers": self._headers(authenticated=authenticated)}
        if params is not None:
            kwargs["params"] = params
        if json_body is not None:
            kwargs["json"] = json_body
        with httpx.Client(timeout=self._timeout) as c:
            response = getattr(c, method.lower())(self._url(path), **kwargs)
            if getattr(response, "status_code", None) == 304:
                return None
            response.raise_for_status()
            content = getattr(response, "content", b"")
            if isinstance(content, str):
                content = content.encode("utf-8")
            body = bytes(content or b"")
            headers = getattr(response, "headers", {})
        return _decode_body(body, headers, allow_empty=allow_empty)

    def _request_bytes(self, path: str, *, authenticated: bool = True) -> bytes:
        with httpx.Client(timeout=self._timeout) as c:
            response = c.get(self._url(path), headers=self._headers(authenticated=authenticated))
            response.raise_for_status()
            content = getattr(response, "content", b"")
            if isinstance(content, str):
                content = content.encode("utf-8")
            body = bytes(content or b"")
        if not body:
            raise RelayResponseError("Relay returned an empty response.")
        if len(body) > MAX_RESPONSE_BYTES:
            raise RelayResponseError("Relay response is too large.")
        return body

    def health(self) -> Dict[str, Any]:
        data = self._request("GET", "/api/health")
        return data if isinstance(data, dict) else {}

    # ---- agent endpoints ----

    def list_uploaded_scans(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            cap = max(1, min(int(limit), MAX_SCAN_ITEMS))
        except (TypeError, ValueError, OverflowError):
            cap = 10
        data = self._request(
            "GET", "/api/agent/scans",
            params={"status": "uploaded", "limit": cap},
        )
        if data is None:  # HTTP 304
            return []
        if isinstance(data, list):
            scans: Any = data
        elif isinstance(data, dict):
            scans = data.get("scans", [])
        else:
            raise RelayResponseError("Relay returned an unexpected scan payload.")
        if not isinstance(scans, (list, tuple)):
            raise RelayResponseError("Relay returned an unexpected scan payload.")
        return list(scans)[:MAX_SCAN_ITEMS]

    def get_catalog(self, since_version: int = 0) -> Optional[Dict[str, Any]]:
        """Fetch a catalog batch; returns None on HTTP 304 (no changes)."""
        data = self._request(
            "GET", "/api/catalog", params={"version": since_version},
        )
        if data is None:
            return None
        if not isinstance(data, dict):
            raise RelayResponseError("Relay returned an unexpected catalog payload.")
        return data

    def download_scan_file(self, scan_id: str) -> bytes:
        path = f"/api/agent/scans/{_scan_path_id(scan_id)}/file"
        return self._request_bytes(path)

    def post_scan_status(
        self, scan_id: str, status: str,
        purchase_reference: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"status": safe_text(status, 20)}
        if purchase_reference is not None:
            body["purchaseReference"] = safe_text(purchase_reference, 50)
        if message is not None:
            body["message"] = safe_text(message, 500)
        path = f"/api/agent/scans/{_scan_path_id(scan_id)}/status"
        result = self._request("POST", path, json_body=body, allow_empty=True)
        return result if isinstance(result, dict) else {}

    def push_catalog(self, version: int, products: List[Dict[str, Any]],
                     base_revision: int = 0) -> Dict[str, Any]:
        payload = {
            "version": version,
            "baseRevision": int(base_revision or 0),
            "products": list(products) if isinstance(products, (list, tuple)) else [],
        }
        result = self._request("PUT", "/api/agent/catalog", json_body=payload, allow_empty=True)
        return result if isinstance(result, dict) else {}

    def create_pairing_session(self) -> Dict[str, Any]:
        data = self._request("POST", "/api/agent/pairing")
        return data if isinstance(data, dict) else {}

    def heartbeat(self) -> Dict[str, Any]:
        data = self._request("POST", "/api/agent/heartbeat", allow_empty=True)
        return data if isinstance(data, dict) else {}

    # ---- bootstrap (one-time setup secret -> agent token) ----

    def bootstrap_agent_token(self, device_id: str = None) -> str:
        if device_id is None:
            from .crypto import compute_device_id
            device_id = compute_device_id()
        data = self._request(
            "POST", "/api/agent/bootstrap",
            json_body={"deviceId": safe_text(device_id, 128)},
            authenticated=False,
        )
        if not isinstance(data, dict):
            raise RelayResponseError("Relay returned an unexpected bootstrap payload.")
        token = data.get("agentToken") or data.get("token")
        if not isinstance(token, str) or not token.strip():
            raise SyncConfigError("Relay did not return an agent token.")
        return token
