import os
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QListWidgetItem, QMessageBox, QGroupBox, QFileDialog,
                               QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Qt
from src.core.backup import BackupManager
from loguru import logger

def Qt_red():
    from PySide6.QtGui import QColor
    return QColor("#c0392b")


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_backups()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Backup Section
        backup_group = QGroupBox("Backup & Recovery")
        backup_layout = QVBoxLayout()

        self.backup_btn = QPushButton("Create Manual Backup")
        self.backup_btn.clicked.connect(self.create_backup)
        backup_layout.addWidget(self.backup_btn)

        backup_layout.addWidget(QLabel("Available Backups (newest first):"))
        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(120)
        self.backup_list.itemSelectionChanged.connect(self._on_backup_selection)
        backup_layout.addWidget(self.backup_list)

        restore_layout = QHBoxLayout()
        self.restore_btn = QPushButton("Restore Selected Backup")
        self.restore_btn.clicked.connect(self.restore_backup)
        self.restore_btn.setEnabled(False)

        self.restore_external_btn = QPushButton("Restore from File...")
        self.restore_external_btn.clicked.connect(self.restore_external)

        restore_layout.addWidget(self.restore_btn)
        restore_layout.addWidget(self.restore_external_btn)
        backup_layout.addLayout(restore_layout)

        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Support & Diagnostics Section
        support_group = QGroupBox("Support & Diagnostics")
        support_layout = QVBoxLayout()
        
        self.btn_export_diagnostics = QPushButton("Export Diagnostic Bundle to Desktop")
        self.btn_export_diagnostics.clicked.connect(self.export_diagnostics)
        support_layout.addWidget(self.btn_export_diagnostics)
        
        support_group.setLayout(support_layout)
        layout.addWidget(support_group)
        
        # Database Maintenance Section
        maintenance_group = QGroupBox("Database Maintenance")
        maintenance_layout = QVBoxLayout()
        
        self.btn_vacuum = QPushButton("Optimize Database (VACUUM)")
        self.btn_vacuum.clicked.connect(self.optimize_database)
        maintenance_layout.addWidget(self.btn_vacuum)
        
        maintenance_group.setLayout(maintenance_layout)
        layout.addWidget(maintenance_group)
        
        # Version Information Section
        version_group = QGroupBox("About Application")
        version_layout = QVBoxLayout()
        
        from src.core.version import APP_NAME, APP_VERSION, BUILD_NUMBER, RELEASE_DATE, get_database_revision
        
        db_rev = get_database_revision()
        
        info = (
            f"<b>{APP_NAME}</b><br><br>"
            f"<b>Version:</b> {APP_VERSION}<br>"
            f"<b>Build:</b> {BUILD_NUMBER}<br>"
            f"<b>Release Date:</b> {RELEASE_DATE}<br>"
            f"<b>Database Revision:</b> {db_rev}<br>"
        )
        
        about_label = QLabel(info)
        about_label.setTextFormat(Qt.RichText)
        version_layout.addWidget(about_label)
        
        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # System Health Section
        health_group = QGroupBox("System Health")
        health_layout = QVBoxLayout()

        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["Check", "Status", "Detail"])
        self.health_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.health_table.verticalHeader().setVisible(False)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.health_table.setMaximumHeight(140)
        health_layout.addWidget(self.health_table)

        self.btn_run_health = QPushButton("Run Health Checks")
        self.btn_run_health.clicked.connect(self.run_health_checks)
        health_layout.addWidget(self.btn_run_health)

        health_group.setLayout(health_layout)
        layout.addWidget(health_group)

        # Website Sync Section
        websync_group = QGroupBox("Website Sync (automatic)")
        websync_layout = QVBoxLayout()

        from src.modules.websync.sync_config import get_sync_folder
        self.sync_folder_label = QLabel(
            f"<b>Sync folder:</b> {get_sync_folder()}<br>"
            "<span style='color:#718096;'>The catalog is refreshed here automatically on every "
            "product/stock change. Drop a <i>price_updates.json</i> file here and it is applied "
            "automatically within 5 minutes.</span>"
        )
        self.sync_folder_label.setTextFormat(Qt.RichText)
        self.sync_folder_label.setWordWrap(True)
        websync_layout.addWidget(self.sync_folder_label)

        folder_row = QHBoxLayout()
        self.btn_change_sync_folder = QPushButton("Change Sync Folder...")
        self.btn_change_sync_folder.clicked.connect(self.change_sync_folder)
        folder_row.addWidget(self.btn_change_sync_folder)
        folder_row.addStretch()
        websync_layout.addLayout(folder_row)

        self.btn_export_catalog = QPushButton("Export Catalog Now...")
        self.btn_export_catalog.clicked.connect(self.export_catalog)
        self.btn_import_prices = QPushButton("Import Price Updates Now...")
        self.btn_import_prices.clicked.connect(self.import_prices)
        websync_layout.addWidget(self.btn_export_catalog)
        websync_layout.addWidget(self.btn_import_prices)

        websync_group.setLayout(websync_layout)
        layout.addWidget(websync_group)

        # Account Security Section
        security_group = QGroupBox("Account Security")
        security_layout = QVBoxLayout()

        self.btn_change_password = QPushButton("Change Password...")
        self.btn_change_password.clicked.connect(self.change_password)
        security_layout.addWidget(self.btn_change_password)

        security_group.setLayout(security_layout)
        layout.addWidget(security_group)

        layout.addStretch()

    def _on_backup_selection(self):
        self.restore_btn.setEnabled(bool(self.backup_list.selectedItems()))

    def refresh_backups(self):
        self.backup_list.clear()
        try:
            backups = BackupManager.list_backups()
            for b in sorted(backups, reverse=True):
                name = os.path.basename(b)
                try:
                    stat = os.stat(b)
                    size_mb = stat.st_size / (1024 * 1024)
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    label = f"{name}   ({modified}  •  {size_mb:.1f} MB)"
                except OSError:
                    label = name
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, name)  # keep raw filename for restore
                self.backup_list.addItem(item)
            self._on_backup_selection()
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")

    def create_backup(self):
        try:
            path = BackupManager.create_backup(prefix="manual")
            QMessageBox.information(self, "Backup Successful", f"Backup created at:\n{path}")
            self.refresh_backups()
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", f"An error occurred:\n{e}")

    def restore_backup(self):
        selected = self.backup_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a backup to restore.")
            return

        filename = selected.data(Qt.UserRole)
        from src.core.paths import BACKUP_DIR
        full_path = os.path.join(str(BACKUP_DIR), filename)

        self._execute_restore(full_path)

    def restore_external(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Backup File", "", "Zip Files (*.zip)")
        if file_path:
            self._execute_restore(file_path)

    def _execute_restore(self, path: str):
        reply = QMessageBox.question(
            self, "Confirm Restore", 
            f"Are you sure you want to restore from {os.path.basename(path)}?\n\nThis will overwrite the current database and the application will close.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                BackupManager.restore_backup(path)
                QMessageBox.information(self, "Restore Successful", "Database restored successfully. The application will now close.")
                import sys
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(self, "Restore Failed", f"Failed to restore database:\n{e}")

    def export_diagnostics(self):
        from src.core.diagnostics import DiagnosticsManager
        try:
            path = DiagnosticsManager.create_diagnostic_bundle()
            QMessageBox.information(self, "Export Successful", f"Diagnostic bundle exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to create diagnostic bundle:\n{e}")

    def optimize_database(self):
        reply = QMessageBox.question(
            self, "Confirm Optimization", 
            "Optimizing the database will reclaim unused disk space. The application will be temporarily locked. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            import sqlite3
            from src.core.paths import DB_PATH
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.isolation_level = None
                conn.execute("VACUUM")
                conn.close()
                QMessageBox.information(self, "Success", "Database optimization completed successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to optimize database:\n{e}")

    def run_health_checks(self):
        from src.core.health_monitor import HealthMonitor, HealthStatus
        try:
            results = HealthMonitor.run_all_checks()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to run health checks:\n{e}")
            return

        colors = {
            HealthStatus.OK.value: "#27ae60",
            HealthStatus.WARN.value: "#e67e22",
            HealthStatus.CRIT.value: "#c0392b",
        }
        from PySide6.QtGui import QColor
        self.health_table.setRowCount(len(results))
        for row, r in enumerate(results):
            name_item = QTableWidgetItem(r["name"])
            status_item = QTableWidgetItem(r["status"])
            status_item.setForeground(QColor(colors.get(r["status"], "#c0392b")))
            detail_item = QTableWidgetItem(r["detail"])
            self.health_table.setItem(row, 0, name_item)
            self.health_table.setItem(row, 1, status_item)
            self.health_table.setItem(row, 2, detail_item)

    def change_sync_folder(self):
        from src.modules.websync.sync_config import get_sync_folder, set_sync_folder
        path = QFileDialog.getExistingDirectory(
            self, "Choose Website Sync Folder", str(get_sync_folder())
        )
        if not path:
            return
        try:
            set_sync_folder(path)
            self.sync_folder_label.setText(
                f"<b>Sync folder:</b> {path}<br>"
                "<span style='color:#718096;'>The catalog is refreshed here automatically on every "
                "product/stock change. Drop a <i>price_updates.json</i> file here and it is applied "
                "automatically within 5 minutes.</span>"
            )
            QMessageBox.information(
                self, "Sync Folder Updated",
                "The website sync folder was updated.\n"
                "Point the website (or its copy task) to this folder."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to change sync folder:\n{e}")

    def export_catalog(self):
        from src.core.session import CurrentSession
        from src.modules.websync.services import WebsiteSyncService
        context = CurrentSession.get_context()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Website Catalog", "website_catalog.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            result = WebsiteSyncService.export_catalog(context, output_path=path)
            QMessageBox.information(
                self, "Export Successful",
                f"{result['count']} products exported to:\n{result['path']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export catalog:\n{e}")

    def import_prices(self):
        from src.core.session import CurrentSession
        from src.modules.websync.services import WebsiteSyncService
        context = CurrentSession.get_context()
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Web Price Updates", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            result = WebsiteSyncService.import_price_updates(context, input_path=path)
            msg = (
                f"Updated {result['updated_count']} prices.\n"
                f"Unknown SKUs skipped: {len(result['unknown_skus'])}\n"
                f"Errors: {len(result['errors'])}"
            )
            if result["errors"]:
                msg += "\n\n" + "\n".join(result["errors"][:5])
            QMessageBox.information(self, "Import Complete", msg)
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import price updates:\n{e}")

    def change_password(self):
        from src.core.session import CurrentSession
        from src.ui.dialogs.auth_dialogs import ChangePasswordDialog
        context = CurrentSession.get_context()
        if not context:
            QMessageBox.warning(self, "Error", "No active session found.")
            return
        dialog = ChangePasswordDialog(username=context.username, parent=self)
        dialog.exec()
