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
    from src.database.session import DB_PATH
    
    # In MVP, drop old SQLite file if we changed schema to avoid alembic migrations for now.
    # To drop the old schema, we can simply delete the DB file or drop_all.
    BaseModel.metadata.drop_all(bind=engine)
    BaseModel.metadata.create_all(bind=engine)
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
