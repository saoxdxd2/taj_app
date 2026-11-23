"""HTTP client for the mobile relay.

Uses httpx. All secrets are read from the credential store, never from
the database or logs. The client never logs request/response bodies
(which may contain ciphertext or tokens).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from .crypto import load_agent_token

logger = logging.getLogger(__name__)


class RelayClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        token = self._token if self._token is not None else load_agent_token()
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(self._url("/api/health"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ---- agent endpoints ----

    def list_uploaded_scans(self, limit: int = 10) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(
                self._url("/api/agent/scans"),
                params={"status": "uploaded", "limit": limit},
                headers=self._headers(),
            )
            r.raise_for_status()
            data = r.json()
            return data.get("scans", data if isinstance(data, list) else [])

    def download_scan_file(self, scan_id: str) -> bytes:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.get(self._url(f"/api/agent/scans/{scan_id}/file"), headers=self._headers())
            r.raise_for_status()
            return r.content

    def post_scan_status(self, scan_id: str, status: str,
                         purchase_reference: Optional[str] = None,
                         message: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"status": status}
        if purchase_reference is not None:
            body["purchaseReference"] = purchase_reference
        if message is not None:
            body["message"] = message
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(self._url(f"/api/agent/scans/{scan_id}/status"),
                       json=body, headers=self._headers())
            r.raise_for_status()
            return r.json() if r.content else {}

    def push_catalog(self, version: int, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.put(self._url("/api/agent/catalog"),
                      json={"version": version, "products": products},
                      headers=self._headers())
            r.raise_for_status()
            return r.json() if r.content else {}

    def create_pairing_session(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(self._url("/api/agent/pairing"), headers=self._headers())
            r.raise_for_status()
            return r.json()

    def heartbeat(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(self._url("/api/agent/heartbeat"), headers=self._headers())
            r.raise_for_status()
            return r.json() if r.content else {}

    # ---- bootstrap (one-time setup secret -> agent token) ----

    def bootstrap_agent_token(self, device_id: str = None) -> str:
        if device_id is None:
            from .crypto import compute_device_id
            device_id = compute_device_id()
        with httpx.Client(timeout=self._timeout) as c:
            r = c.post(self._url("/api/agent/bootstrap"),
                       json={"deviceId": device_id},
                       headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
            token = data.get("agentToken") or data.get("token")
            if not token:
                raise RuntimeError("Relay did not return an agent token.")
            return token