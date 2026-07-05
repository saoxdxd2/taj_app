import os
from pathlib import Path

# Use %LOCALAPPDATA% if available (Windows), otherwise fallback to home directory
local_app_data = os.environ.get("LOCALAPPDATA")
if local_app_data:
    BASE_DATA_DIR = Path(local_app_data) / "TAJ_FROID"
else:
    BASE_DATA_DIR = Path.home() / ".taj_froid"

# Define the standard directories
DB_DIR = BASE_DATA_DIR / "data"
LOG_DIR = BASE_DATA_DIR / "logs"
BACKUP_DIR = BASE_DATA_DIR / "backups"
CONFIG_DIR = BASE_DATA_DIR / "config"
TEMP_DIR = BASE_DATA_DIR / "temp"

# Ensure all directories exist
for directory in [DB_DIR, LOG_DIR, BACKUP_DIR, CONFIG_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Specific file paths
DB_PATH = DB_DIR / "taj_froid.db"
LOG_FILE_PATH = LOG_DIR / "app.log"
