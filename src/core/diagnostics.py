import os
import sys
import platform
import zipfile
import sqlite3
import tempfile
from datetime import datetime
from loguru import logger
from src.core.paths import BASE_DATA_DIR, DB_PATH, LOG_FILE_PATH, TEMP_DIR
from src.core.version import APP_VERSION, BUILD_NUMBER, get_database_revision

class DiagnosticsManager:
    @staticmethod
    def create_diagnostic_bundle() -> str:
        """
        Gathers logs, database metadata, and system info into a single zip file.
        Returns the path to the zip file.
        """
        logger.info("Generating diagnostic bundle...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        bundle_filename = f"taj_froid_diagnostics_{timestamp}.zip"
        
        # Prefer the desktop for easy user access, but fall back to the
        # application data directory when there is no Desktop folder or it
        # is read-only (locked-down shop PC, redirected/OneDrive profile).
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        candidate_dirs = []
        if os.path.isdir(desktop_path):
            candidate_dirs.append(desktop_path)
        candidate_dirs.append(os.path.join(str(BASE_DATA_DIR), "diagnostics"))

        bundle_path = None
        for directory in candidate_dirs:
            try:
                os.makedirs(directory, exist_ok=True)
                probe = os.path.join(directory, ".taj_write_test")
                with open(probe, "w", encoding="utf-8"):
                    pass
                os.remove(probe)
            except OSError:
                continue
            bundle_path = os.path.join(directory, bundle_filename)
            break

        if bundle_path is None:
            raise OSError("No writable location for the diagnostic bundle.")

        with tempfile.TemporaryDirectory(dir=str(TEMP_DIR)) as temp_dir:
            # 1. System Info
            info_path = os.path.join(temp_dir, "system_info.txt")
            with open(info_path, 'w', encoding="utf-8") as f:
                f.write(f"App Version: {APP_VERSION}\n")
                f.write(f"Build Number: {BUILD_NUMBER}\n")
                f.write(f"DB Revision: {get_database_revision()}\n")
                f.write(f"OS: {platform.system()} {platform.release()} ({platform.version()})\n")
                f.write(f"Python: {sys.version}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                
            # 2. Database Stats
            db_stats_path = os.path.join(temp_dir, "db_stats.txt")
            try:
                if os.path.exists(DB_PATH):
                    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
                    with open(db_stats_path, 'w', encoding="utf-8") as f:
                        f.write(f"Database Size: {size_mb:.2f} MB\n\n")
                        
                        import contextlib
                        with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
                            cursor = conn.cursor()
                            
                            # Get row counts for all tables
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                            tables = cursor.fetchall()
                            for table in tables:
                                table_name = table[0]
                                # Table names cannot be bound as parameters,
                                # so the identifier is quoted instead. An
                                # unquoted f-string here would execute SQL
                                # from any table name containing a quote.
                                quoted = '"' + table_name.replace('"', '""') + '"'
                                cursor.execute(f"SELECT count(*) FROM {quoted}")
                                count = cursor.fetchone()[0]
                                f.write(f"Table {table_name}: {count} rows\n")
            except Exception as e:
                logger.error(f"Failed to gather DB stats: {e}")

            # 3. Zip it all up
            try:
                with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(info_path, arcname="system_info.txt")
                    if os.path.exists(db_stats_path):
                        zipf.write(db_stats_path, arcname="db_stats.txt")

                    # We can't safely zip the active log file if it's locked,
                    # but loguru usually allows read.
                    if os.path.exists(LOG_FILE_PATH):
                        try:
                            zipf.write(LOG_FILE_PATH, arcname="app.log")
                        except Exception as e:
                            logger.warning(
                                f"Could not include app.log in diagnostic bundle: {e}"
                            )
            except Exception:
                # Do not leave a half-written bundle that support may
                # mistake for a complete one.
                if os.path.exists(bundle_path):
                    try:
                        os.remove(bundle_path)
                    except OSError:
                        pass
                raise

        logger.info(f"Diagnostic bundle created at {bundle_path}")
        return bundle_path
