from src.core.context import RequestContext
import logging

logger = logging.getLogger(__name__)

class AccessDenied(Exception):
    """Raised when a user lacks the necessary permission to perform an action."""
    pass

class PermissionManager:
    """
    Manages and verifies hierarchical permissions.
    """

    @staticmethod
    def verify_permission(context: RequestContext, required_permission: str):
        """
        Verifies if the context holds the required permission or a wildcard match.
        Example: required_permission="Inventory.Products.Create"
                 context.permissions={"Inventory.*"} -> Access Granted
                 context.permissions={"Everything"} -> Access Granted (Admin)
        """
        # Admin / superuser override — both '.*' and 'Everything' grant full access
        if "Everything" in context.permissions or ".*" in context.permissions:
            return True
            
        # Exact match
        if required_permission in context.permissions:
            return True
            
        # Wildcard match (e.g., 'Inventory.*' matches 'Inventory.Products.Create')
        parts = required_permission.split('.')
        for i in range(1, len(parts)):
            wildcard = ".".join(parts[:i]) + ".*"
            if wildcard in context.permissions:
                return True
                
        logger.warning(f"AccessDenied: User {context.username} ({context.user_id}) "
                       f"attempted to access {required_permission} without permission.")
        raise AccessDenied(f"Access Denied: Missing permission '{required_permission}'")

