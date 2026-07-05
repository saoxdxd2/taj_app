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
    
    BaseModel.metadata.create_all(bind=engine)
    session_maker = get_session_maker()
    
    with session_maker() as session:
        # Create default admin if not exists
        admin = session.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=AuthenticationService.hash_password("admin"),
                role=Role.ADMINISTRATOR
            )
            session.add(admin)
            session.commit()

def main():
    app = QApplication(sys.argv)
    
    # Initialize DB and ensure default admin exists
    init_db()
    session_maker = get_session_maker()

    # Show Login Gateway
    login = LoginDialog(session_maker)
    if login.exec() == LoginDialog.Accepted:
        window = MainWindow(session_maker)
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
