import sys
from PySide6.QtWidgets import QApplication

from src.database.config import get_session_maker
from src.database.base import BaseModel, engine
from src.modules.authentication.models import User, Role
from src.modules.authentication.services import AuthenticationService

from src.ui.main_window import MainWindow, LoginDialog

def init_db():
    # Import all models to ensure they are registered with BaseModel.metadata
    import src.modules.inventory.models
    import src.modules.crm.models
    import src.modules.suppliers.models
    import src.modules.purchasing.models
    import src.modules.sales.models
    import src.modules.finance.models
    import src.modules.audit.models
    import os
    import sys
    import shutil
    from datetime import datetime
    from PySide6.QtWidgets import QMessageBox
    from src.core.paths import DB_PATH, BACKUP_DIR
    from alembic import command
    from alembic.config import Config

    from loguru import logger
    from src.core.logging import setup_logging
    
    # Initialize enterprise logging
    setup_logging()

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

    from src.core.backup import BackupManager

    # Pre-migration backup logic
    if os.path.exists(DB_PATH):
        try:
            backup_path = BackupManager.create_backup(prefix="pre_migration")
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Startup aborted: Pre-migration backup failed.")
            msg.setInformativeText(f"Could not secure database backup.\nError: {str(e)}")
            msg.setWindowTitle("Fatal Error")
            msg.exec()
            sys.exit(1)

    # Programmatic Alembic upgrade
    try:
        logger.info("Executing database migrations...")
        # Get path to alembic.ini relative to this file
        project_root = os.path.dirname(os.path.abspath(__file__))
        alembic_ini_path = os.path.join(project_root, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        # Override the sqlalchemy.url dynamically
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
        
        # Run the upgrade
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("The database could not be upgraded safely.")
        msg.setInformativeText("No changes have been applied. Please contact support.\n\n" + str(e))
        msg.setWindowTitle("Fatal Error")
        msg.exec()
        sys.exit(1)
        
    session_maker = get_session_maker()
    
    with session_maker() as session:
        from src.modules.authentication.models import Role, Permission
        
        # 1. Seed Permissions
        admin_perm = session.query(Permission).filter(Permission.name == ".*").first()
        if not admin_perm:
            admin_perm = Permission(name=".*", description="Superuser access")
            session.add(admin_perm)
            
        manager_perms = ["Inventory.*", "CRM.*", "Suppliers.*", "Sales.*", "Purchasing.*"]
        manager_perm_objs = []
        for p_name in manager_perms:
            p_obj = session.query(Permission).filter(Permission.name == p_name).first()
            if not p_obj:
                p_obj = Permission(name=p_name, description=f"Manager access for {p_name}")
                session.add(p_obj)
            manager_perm_objs.append(p_obj)
            
        employee_perms = ["Inventory.Products.View", "CRM.Customers.View", "Sales.Invoices.Create"]
        employee_perm_objs = []
        for p_name in employee_perms:
            p_obj = session.query(Permission).filter(Permission.name == p_name).first()
            if not p_obj:
                p_obj = Permission(name=p_name, description=f"Employee access for {p_name}")
                session.add(p_obj)
            employee_perm_objs.append(p_obj)
            
        session.flush()

        # 2. Seed Roles
        role_admin = session.query(Role).filter(Role.name == "Administrator").first()
        if not role_admin:
            role_admin = Role(name="Administrator", description="System Administrator")
            role_admin.permissions.append(admin_perm)
            session.add(role_admin)
            
        role_manager = session.query(Role).filter(Role.name == "Manager").first()
        if not role_manager:
            role_manager = Role(name="Manager", description="Department Manager")
            role_manager.permissions.extend(manager_perm_objs)
            session.add(role_manager)
            
        role_employee = session.query(Role).filter(Role.name == "Employee").first()
        if not role_employee:
            role_employee = Role(name="Employee", description="Standard Employee")
            role_employee.permissions.extend(employee_perm_objs)
            session.add(role_employee)
            
        session.flush()

        # 3. Create default admin if not exists
        admin = session.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=AuthenticationService.hash_password("admin"),
                role_id=role_admin.id
            )
            session.add(admin)
            
        session.commit()

def main():
    app = QApplication(sys.argv)
    
    # Initialize DB and ensure default admin exists
    init_db()
    session_maker = get_session_maker()

    # Add automatic backup on shutdown
    def shutdown_backup():
        from src.core.backup import BackupManager
        from loguru import logger
        try:
            logger.info("Application shutting down. Initiating automatic backup...")
            BackupManager.create_backup(prefix="shutdown")
        except Exception as e:
            logger.error(f"Shutdown backup failed: {e}")

    app.aboutToQuit.connect(shutdown_backup)

    # Show Login Gateway
    login = LoginDialog()
    if login.exec() == LoginDialog.Accepted:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
