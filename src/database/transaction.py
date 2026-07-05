import functools
import inspect
from typing import Callable, Any

def transactional(func: Callable) -> Callable:
    """
    Decorator that manages the SQLAlchemy session lifecycle for Service layer methods.
    
    - If `session` is provided (positionally or via kwargs), the method participates 
      in the existing transaction.
    - If `session` is NOT provided, a new SessionLocal is created, injected into kwargs,
      and the method becomes the transaction boundary (commits on success, rolls back on exception).
      
    This completely abstracts transaction management away from the UI layer, without
    requiring changes to the Service method signatures.
    """
    sig = inspect.signature(func)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        bound_args = sig.bind_partial(*args, **kwargs)
        session = bound_args.arguments.get('session')
        is_new_session = False
        
        if session is None:
            from src.database.session import SessionLocal
            session = SessionLocal()
            kwargs['session'] = session
            is_new_session = True
            
        try:
            result = func(*args, **kwargs)
            if is_new_session:
                session.commit()
            return result
        except Exception:
            if is_new_session:
                session.rollback()
            raise
        finally:
            if is_new_session:
                session.close()
                
    return wrapper
