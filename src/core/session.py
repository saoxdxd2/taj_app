from typing import Optional
from src.core.context import RequestContext

class CurrentSession:
    """
    Singleton holding the active user's session state.
    Provides the RequestContext to all UI components.
    """
    _instance = None
    _context: Optional[RequestContext] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CurrentSession, cls).__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, context: RequestContext):
        """Initializes the session upon successful login."""
        cls._context = context

    @classmethod
    def get_context(cls) -> RequestContext:
        """Retrieves the current execution context."""
        if cls._context is None:
            raise RuntimeError("Session has not been initialized. User is not logged in.")
        return cls._context

    @classmethod
    def clear(cls):
        """Clears the session on logout."""
        cls._context = None
