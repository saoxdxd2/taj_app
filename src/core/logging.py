import sys
import traceback
from loguru import logger
from src.core.paths import LOG_FILE_PATH

def setup_logging():
    """
    Configures enterprise-grade logging for the application.
    Removes the default handler, adds a file handler with rotation and retention.
    Also hooks into sys.excepthook to catch unhandled UI exceptions.
    """
    # Remove default stderr handler to prevent console clutter if not needed
    # or keep it for debugging. We'll remove and add a clean one.
    logger.remove()
    
    # Add console logger (optional, helpful for dev)
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    
    # Add rotating file logger in the %LOCALAPPDATA% directory
    logger.add(
        str(LOG_FILE_PATH),
        rotation="10 MB",       # Rotate when file reaches 10MB
        retention="30 days",    # Keep logs for 30 days
        compression="zip",      # Compress rotated logs
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        backtrace=True,         # Extended traceback
        diagnose=True           # Local variable values in tracebacks
    )

    # Global unhandled exception hook
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    
    logger.info("Enterprise logging initialized.")
