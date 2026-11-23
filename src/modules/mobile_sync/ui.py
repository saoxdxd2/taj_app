"""Mobile inbox + configuration UI.

Shows scans awaiting review, configures the relay URL, bootstraps the
agent token, creates pairing sessions (QR code), and triggers sync.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QLineEdit, QGroupBox, QFormLayout, QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from src.core.session import CurrentSession
from src.core.paths import CONFIG_DIR
from src.modules.mobile_sync.agent import MobileAgent
from src.modules.mobile_sync.client import RelayClient
from src.modules.mobile_sync.crypto import (
    ensure_keypair, public_key_b64, load_agent_token, store_agent_token,
    delete_agent_token,
)
from src.modules.mobile_sync.models import MobileScan, MobileScanState
from src.modules.mobile_sync.sync import load_state, push_catalog, pull_catalog

logger = logging.getLogger(__name__)


class MobileInboxWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = CurrentSession.get_context()
        self._agent: Optional[MobileAgent] = None
        self._pending: list = []
        self._relay_url = self._load_relay_url()
        self.setup_ui()
        self.refresh_list()

    # ---- config persistence ----

    def _config_file(self):
        return CONFIG_DIR / "mobile_relay.json"

    def _load_relay_url(self) -> str:
        try:
            import json
            data = json.loads(self._config_file().read_text(encoding="utf-8"))
            return data.get("relay_url", "")
        except (OSError, ValueError):
            return ""

    def _save_relay_url(self, url: str) -> None:
        import json
        try:
            self._config_file().write_text(json.dumps({"relay_url": url}, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save relay URL: %s", exc)

    def _client(self) -> Optional[RelayClient]:
        if not self._relay_url:
            return None
        token = load_agent_token()
        return RelayClient(self._relay_url, token=token)

    # ---- UI ----

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Config group
        cfg = QGroupBox("Relay configuration")
        form = QFormLayout(cfg)

        self.inp_url = QLineEdit(self._relay_url)
        self.inp_url.setPlaceholderText("https://your-relay.vercel.app")
        form.addRow("Relay URL", self.inp_url)

        url_row = QHBoxLayout()
        self.btn_save_url = QPushButton("Save URL")
        self.btn_save_url.clicked.connect(self._on_save_url)
        url_row.addWidget(self.btn_save_url)
        url_row.addStretch()
        form.addRow("", url_row)

        self.lbl_token = QLabel("Agent token: " + ("set" if load_agent_token() else "NOT set"))
        form.addRow("", self.lbl_token)

        self.inp_secret = QLineEdit()
        self.inp_secret.setEchoMode(QLineEdit.Password)
        self.inp_secret.setPlaceholderText("One-time setup secret (ERP_SETUP_SECRET)")
        form.addRow("Setup secret", self.inp_secret)

        self.btn_bootstrap = QPushButton("Bootstrap agent token")
        self.btn_bootstrap.clicked.connect(self._on_bootstrap)
        form.addRow("", self.btn_bootstrap)

        self.btn_pair = QPushButton("Create pairing session (QR)")
        self.btn_pair.clicked.connect(self._on_pair)
        form.addRow("", self.btn_pair)

        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        form.addRow("Pairing QR", self.lbl_qr)

        self.btn_delete_token = QPushButton("Delete agent token")
        self.btn_delete_token.clicked.connect(self._on_delete_token)
        form.addRow("", self.btn_delete_token)

        layout.addWidget(cfg)

        # Sync group
        sync = QGroupBox("Sync")
        sync_layout = QHBoxLayout(sync)
        self.btn_push = QPushButton("Push catalog now")
        self.btn_push.clicked.connect(self._on_push)
        self.btn_pull = QPushButton("Pull remote catalog")
        self.btn_pull.clicked.connect(self._on_pull)
        self.btn_start_agent = QPushButton("Start agent")
        self.btn_start_agent.clicked.connect(self._on_start_agent)
        self.btn_stop_agent = QPushButton("Stop agent")
        self.btn_stop_agent.clicked.connect(self._on_stop_agent)
        sync_layout.addWidget(self.btn_push)
        sync_layout.addWidget(self.btn_pull)
        sync_layout.addWidget(self.btn_start_agent)
        sync_layout.addWidget(self.btn_stop_agent)
        sync_layout.addStretch()
        layout.addWidget(sync)

        self.lbl_status = QLabel("idle")
        layout.addWidget(self.lbl_status)

        # Inbox list
        layout.addWidget(QLabel("Mobile scans (inbox)"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_open = QPushButton("Open / Review")
        self.btn_open.setEnabled(False)
        btns.addWidget(self.btn_refresh)
        btns.addWidget(self.btn_open)
        btns.addStretch()
        layout.addLayout(btns)
        self.btn_refresh.clicked.connect(self.refresh_list)
        self.btn_open.clicked.connect(self.open_selected)
        self.list_widget.itemSelectionChanged.connect(
            lambda: self.btn_open.setEnabled(bool(self.list_widget.selectedItems()))
        )

    # ---- handlers ----

    def _on_save_url(self):
        url = self.inp_url.text().strip().rstrip("/")
        self._relay_url = url
        self._save_relay_url(url)
        self.lbl_status.setText(f"Relay URL saved: {url}")

    def _on_bootstrap(self):
        client = RelayClient(self._relay_url)
        secret = self.inp_secret.text().strip()
        if not secret:
            QMessageBox.warning(self, "Missing secret", "Enter the setup secret.")
            return
        try:
            token = client.bootstrap_agent_token(secret)
            store_agent_token(token)
            self.lbl_token.setText("Agent token: set")
            self.lbl_status.setText("Agent token bootstrapped.")
        except Exception as exc:
            QMessageBox.critical(self, "Bootstrap failed", str(exc))

    def _on_delete_token(self):
        delete_agent_token()
        self.lbl_token.setText("Agent token: NOT set")
        self.lbl_status.setText("Agent token deleted.")

    def _on_pair(self):
        client = self._client()
        if client is None:
            QMessageBox.warning(self, "No relay", "Save a relay URL first.")
            return
        try:
            session = client.create_pairing_session()
            code = session.get("pairingCode", "")
            priv, pub = ensure_keypair()
            payload = {
                "relay": self._relay_url,
                "code": code,
                "publicKey": public_key_b64(),
                "version": 1,
            }
            import json as _json
            qr_text = _json.dumps(payload)
            self._show_qr(qr_text)
            self.lbl_status.setText(f"Pairing session created. Code: {code}")
        except Exception as exc:
            QMessageBox.critical(self, "Pairing failed", str(exc))

    def _show_qr(self, text: str):
        try:
            import qrcode
            img = qrcode.make(text)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pm = QPixmap()
            pm.loadFromData(buf.getvalue())
            self.lbl_qr.setPixmap(pm.scaled(200, 200, Qt.KeepAspectRatio))
        except Exception as exc:
            self.lbl_qr.setText(f"QR error: {exc}\n{text}")

    def _on_push(self):
        client = self._client()
        if client is None:
            QMessageBox.warning(self, "No relay", "Save a relay URL first.")
            return
        try:
            result = push_catalog(self.context, client)
            self.lbl_status.setText(f"Pushed catalog: {result}")
        except Exception as exc:
            QMessageBox.critical(self, "Push failed", str(exc))

    def _on_pull(self):
        client = self._client()
        if client is None:
            QMessageBox.warning(self, "No relay", "Save a relay URL first.")
            return
        try:
            from src.modules.mobile_sync.sync import pull_catalog, diff_catalog
            state = load_state()
            since = state.get("last_pulled_version", 0)
            new_version, products = pull_catalog(client, since)
            self.lbl_status.setText(f"Pulled: version {new_version}, {len(products)} products.")
        except Exception as exc:
            QMessageBox.critical(self, "Pull failed", str(exc))

    def _on_start_agent(self):
        if self._agent is not None:
            return
        if not self._relay_url:
            QMessageBox.warning(self, "No relay", "Save a relay URL first.")
            return
        self._agent = MobileAgent(self._relay_url, self.context)
        self._agent.new_scan_ready.connect(self._on_new_scan)
        self._agent.scan_failed.connect(self._on_scan_failed)
        self._agent.status.connect(lambda s: self.lbl_status.setText(f"agent: {s}"))
        self._agent.start()
        self.lbl_status.setText("Agent started.")

    def _on_stop_agent(self):
        if self._agent is not None:
            self._agent.stop()
            self._agent.wait(5000)
            self._agent = None
            self.lbl_status.setText("Agent stopped.")

    def _on_new_scan(self, row, invoice_scan):
        self._pending.append((row, invoice_scan))
        self.refresh_list()

    def _on_scan_failed(self, relay_id: str, message: str):
        QMessageBox.warning(self, "Mobile scan failed", f"{relay_id}: {message}")

    def refresh_list(self):
        from src.database.session import SessionLocal
        with SessionLocal() as session:
            rows = (
                session.query(MobileScan)
                .filter(MobileScan.status.in_([
                    MobileScanState.NEEDS_REVIEW.value,
                    MobileScanState.FETCHED.value,
                    MobileScanState.EXTRACTED.value,
                ]))
                .order_by(MobileScan.id.desc())
                .all()
            )
            self.list_widget.clear()
            for row in rows:
                item = QListWidgetItem(f"{row.relay_scan_id} — {row.status}")
                item.setData(Qt.UserRole, row.relay_scan_id)
                self.list_widget.addItem(item)

    def open_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        relay_id = item.data(Qt.UserRole)
        pending = next((p for p in self._pending if getattr(p[0], "relay_scan_id", None) == relay_id), None)
        if pending is None:
            QMessageBox.information(self, "Not ready", "This scan is not yet extracted.")
            return
        _row, invoice_scan = pending
        QMessageBox.information(
            self, "Review on PC",
            "Open the Purchases screen to review and save this scan as a DRAFT purchase.",
        )

    def stop_agent(self):
        self._on_stop_agent()