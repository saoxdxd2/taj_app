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

        self.lbl_device = QLabel("Device ID: " + __import__("src.modules.mobile_sync.crypto", fromlist=["compute_device_id"]).compute_device_id()[:16] + "...")
        form.addRow("", self.lbl_device)

        self.btn_bootstrap = QPushButton("Auto-connect (no secret needed)")
        self.btn_bootstrap.clicked.connect(self._on_bootstrap)
        form.addRow("", self.btn_bootstrap)

        self.btn_pair = QPushButton("Create pairing session (QR)")
        self.btn_pair.clicked.connect(self._on_pair)
        form.addRow("", self.btn_pair)

        self.btn_delete_token = QPushButton("Delete agent token")
        self.btn_delete_token.clicked.connect(self._on_delete_token)
        form.addRow("", self.btn_delete_token)

        layout.addWidget(cfg)

        # QR code displayed in its own centered area (not constrained by form layout)
        qr_group = QGroupBox("Pairing QR")
        qr_layout = QVBoxLayout(qr_group)
        qr_layout.setAlignment(Qt.AlignCenter)
        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        self.lbl_qr.setFixedSize(400, 400)
        qr_layout.addWidget(self.lbl_qr, alignment=Qt.AlignCenter)
        self.lbl_qr_hint = QLabel("Click 'Create pairing session' to generate a QR code")
        self.lbl_qr_hint.setAlignment(Qt.AlignCenter)
        qr_layout.addWidget(self.lbl_qr_hint, alignment=Qt.AlignCenter)
        layout.addWidget(qr_group)

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
        try:
            token = client.bootstrap_agent_token()
            store_agent_token(token)
            self.lbl_token.setText("Agent token: set")
            self.lbl_status.setText("Agent token auto-connected.")
        except Exception as exc:
            QMessageBox.critical(self, "Auto-connect failed", str(exc))

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
            import urllib.parse
            params = urllib.parse.urlencode({
                "relay": self._relay_url,
                "code": code,
                "pk": public_key_b64(),
                "v": "1",
            })
            qr_text = f"{self._relay_url}/pair?{params}"
            self._show_qr(qr_text)
            self.lbl_status.setText(f"Pairing session created. Code: {code}")
        except Exception as exc:
            QMessageBox.critical(self, "Pairing failed", str(exc))

    def _show_qr(self, text: str):
        try:
            import qrcode
            qr = qrcode.QRCode(version=None, box_size=8, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pm = QPixmap()
            pm.loadFromData(buf.getvalue())
            # Scale to fit the label while keeping aspect ratio
            self.lbl_qr.setPixmap(pm.scaled(380, 380, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_qr_hint.setText("Scan this QR code with your phone camera")
        except Exception as exc:
            self.lbl_qr.setText(f"QR error: {exc}")

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