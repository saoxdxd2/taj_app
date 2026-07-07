import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QListWidget, QMessageBox, QGroupBox, QFileDialog)
from PySide6.QtCore import Qt
from src.core.backup import BackupManager
from loguru import logger

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
        
        self.backup_list = QListWidget()
        backup_layout.addWidget(QLabel("Available Backups:"))
        backup_layout.addWidget(self.backup_list)
        
        restore_layout = QHBoxLayout()
        self.restore_btn = QPushButton("Restore Selected Backup")
        self.restore_btn.clicked.connect(self.restore_backup)
        
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

        # Account Security Section
        security_group = QGroupBox("Account Security")
        security_layout = QVBoxLayout()

        self.btn_change_password = QPushButton("Change Password...")
        self.btn_change_password.clicked.connect(self.change_password)
        security_layout.addWidget(self.btn_change_password)

        security_group.setLayout(security_layout)
        layout.addWidget(security_group)

        layout.addStretch()

    def refresh_backups(self):
        self.backup_list.clear()
        try:
            backups = BackupManager.list_backups()
            for b in backups:
                self.backup_list.addItem(os.path.basename(b))
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
            
        filename = selected.text()
        from src.core.paths import BACKUP_DIR
        full_path = os.path.join(BACKUP_DIR, filename)
        
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

    def change_password(self):
        from src.core.session import CurrentSession
        from src.ui.dialogs.auth_dialogs import ChangePasswordDialog
        context = CurrentSession.get_context()
        if not context:
            QMessageBox.warning(self, "Error", "No active session found.")
            return
        dialog = ChangePasswordDialog(username=context.username, parent=self)
        dialog.exec()
