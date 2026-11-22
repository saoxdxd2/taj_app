import os
import sys

# Silence Qt's "Cannot find font directory" console warning by pointing
# it at the Windows system fonts (Qt no longer bundles fonts).
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

# A packaged build is a production build. Set the environment before any
# settings module is imported so logging, redaction and health checks use
# production defaults even when no .env file was shipped. An explicit
# TAJ_ENVIRONMENT variable still wins, which keeps local debugging possible.
if getattr(sys, "frozen", False):
    os.environ.setdefault("TAJ_ENVIRONMENT", "production")

from loguru import logger
from PySide6.QtWidgets import QApplication, QMessageBox


def init_db():
    from PySide6.QtWidgets import QMessageBox

    from src.core.logging import setup_logging

    # Initialize enterprise logging before importing the model graph, so an
    # import failure is captured in the log and reported by main().
    setup_logging()

    # Import all models to ensure they are registered with BaseModel.metadata
    import src.modules.inventory.models
    import src.modules.crm.models
    import src.modules.suppliers.models
    import src.modules.purchasing.models
    import src.modules.sales.models
    import src.modules.finance.models
    import src.modules.accounting.models
    import src.modules.audit.models

    # --- HEALTH CHECK ENGINE ---
    from src.core.health_check import HealthCheckEngine, HealthStatus
    health_results = HealthCheckEngine.run_all()
    
    fatals = [r for r in health_results if r.status == HealthStatus.FATAL]
    warnings = [r for r in health_results if r.status == HealthStatus.WARNING]

    if fatals:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Startup Aborted - System Health Failure")
        text = "The application cannot start safely due to critical infrastructure failures:\n\n"
        for f in fatals:
            text += f"• {f.component}: {f.message}\n"
        msg.setText(text)
        msg.setInformativeText("Please contact technical support immediately to prevent data loss.")
        msg.exec()
        sys.exit(1)

    if warnings:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("System Health Warning")
        text = "The application is starting in a degraded state:\n\n"
        for w in warnings:
            text += f"• {w.component}: {w.message}\n"
        msg.setText(text)
        msg.setInformativeText("Some features (like backups) may be disabled, but you can continue working.")
        msg.exec()
    # --- END HEALTH CHECK ---

    from src.core.migrations import apply_migrations
    from src.ui.dialogs.migration_dialog import MigrationErrorDialog

    # Programmatic Alembic upgrade, with recovery on failure.
    result = apply_migrations()
    if not result.success:
        dialog = MigrationErrorDialog(
            error=result.error or "Unknown migration error.",
            backup_path=result.backup_path,
        )
        dialog.exec()

        if dialog.choice == MigrationErrorDialog.RESTORE and result.backup_path:
            try:
                from src.core.backup import BackupManager
                BackupManager.restore_backup(result.backup_path)
            except Exception as restore_error:
                logger.error(f"Restore failed: {restore_error}")
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Restore Failed")
                msg.setText("The backup could not be restored automatically.")
                msg.setInformativeText(str(restore_error))
                msg.exec()
                sys.exit(1)
            # The restored database is back at its original revision, which
            # may not match the schema this binary expects. Exit cleanly and
            # let the user restart (or install the matching release) rather
            # than running the new code against an old schema.
            logger.info("Database restored from pre-migration backup.")
            QMessageBox.information(
                None,
                "Database Restored",
                "The pre-upgrade backup was restored successfully.\n\n"
                "The application will now close. Restart it, or install the "
                "release that matches this database if the upgrade fails again.",
            )
            sys.exit(0)
        elif dialog.choice == MigrationErrorDialog.RETRY:
            second = apply_migrations()
            if not second.success:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Database Upgrade Failed")
                msg.setText("The database could not be upgraded safely.")
                msg.setInformativeText(
                    "Please contact support and restore a backup.\n\n"
                    + (second.error or "")
                )
                msg.exec()
                sys.exit(1)
        else:
            sys.exit(1)
        
    from src.database.session import SessionLocal

    session_maker = SessionLocal

    with session_maker() as session:
        # Reconcile the full permission catalog and built-in role grants on
        # every start, not only when the rows are missing. This is what
        # makes a permission added in a later release visible to existing
        # installations.
        from src.modules.authentication.bootstrap import initialize_security

        initialize_security(session)
        session.commit()

def _start_local_operator_session():
    """Signs the application in as the local Administrator.

    The desktop build is single-operator and has no login screen. The
    service layer and the audit trail still require a RequestContext, so
    this attaches the first active Administrator account. Roles and
    permission checks keep working exactly as before.
    """
    from src.core.context import RequestContext
    from src.core.session import CurrentSession
    from src.database.session import SessionLocal
    from src.modules.authentication.models import Role, User
    from src.modules.authentication.services import AuthenticationService

    with SessionLocal() as session:
        admin_role = (
            session.query(Role)
            .filter(Role.name == AuthenticationService.ADMIN_ROLE)
            .first()
        )
        if admin_role is None:
            raise RuntimeError(
                "Administrator role is missing; security bootstrap did not run."
            )

        admins = (
            session.query(User)
            .filter(User.role_id == admin_role.id)
            .order_by(User.id)
            .all()
        )
        if not admins:
            raise RuntimeError("No Administrator account exists in the database.")

        user = next((u for u in admins if u.is_active), admins[0])

        CurrentSession.initialize(RequestContext(
            user_id=str(user.id),
            username=user.username,
            role=user.role.name,
            permissions={p.name for p in user.role.permissions},
            workstation="Local",
        ))

        if not user.is_active:
            user.is_active = True
            session.commit()
            logger.warning(
                f"Re-activated Administrator '{user.username}' for the local session."
            )

        logger.info(f"Local session started as Administrator '{user.username}'.")


def _startup(app):
    """Builds and shows the application, returning the main window.

    The caller must keep the returned window alive for the lifetime of the
    Qt event loop; otherwise its Python wrapper can be garbage-collected
    while the window is still visible.
    """
    # Initialize DB and ensure default admin exists. Logging is configured
    # inside init_db, so a later UI import failure has a traceback in the
    # log and can be reported through the startup-failure dialog.
    init_db()

    # Apply the global visual theme before any window is created.
    from src.ui.theme import apply_theme
    apply_theme(app)

    # Every widget reads CurrentSession in its constructor, so the local
    # operator session must exist before the main window is built.
    _start_local_operator_session()

    # Import the UI only after logging and the database are ready. If a
    # widget module is broken, main() can still log the traceback and show
    # the startup-failure dialog instead of dying during module import.
    from src.ui.main_window import MainWindow

    # Start automatic website synchronization (catalog auto-export +
    # pending price-update auto-import)
    try:
        from src.modules.websync.auto import setup_auto_sync
        setup_auto_sync()
    except Exception as e:
        logger.error(f"Website auto-sync failed to start: {e}")

    # Add automatic backup on shutdown
    def shutdown_backup():
        from src.core.backup import BackupManager
        try:
            logger.info("Application shutting down. Initiating automatic backup...")
            # Release pooled SQLite connections first: an open connection
            # can keep the file locked and make the final snapshot fail.
            from src.database.session import engine
            engine.dispose()
            BackupManager.create_backup(prefix="shutdown")
        except Exception as e:
            logger.error(f"Shutdown backup failed: {e}")

    app.aboutToQuit.connect(shutdown_backup)

    window = MainWindow()
    window.show()
    return window


def main():
    app = QApplication(sys.argv)

    main_window = None
    try:
        # Hold the main window for the lifetime of the event loop. Without
        # this reference the Python wrapper can be garbage-collected right
        # after show(), destroying the window while it is still in use.
        main_window = _startup(app)
    except SystemExit:
        # Intentional exits from the setup/login/migration dialogs.
        raise
    except Exception as exc:
        # A packaged GUI app has no console. Log the traceback and tell the
        # user what happened instead of disappearing with no explanation.
        logger.exception("Fatal error during application startup")
        try:
            QMessageBox.critical(
                None,
                "Startup Failed",
                "TAJ FROID ERP could not start.\n\n"
                f"{exc}\n\n"
                "The details were written to the application log. "
                "Do not delete the database; contact support or restore a backup.",
            )
        except Exception:
            # The dialog itself must never mask the original failure.
            pass
        sys.exit(1)

    try:
        exit_code = app.exec()
    except Exception:
        logger.exception("Fatal error while running the application")
        exit_code = 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
