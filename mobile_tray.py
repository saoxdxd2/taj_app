"""Launcher for the mobile sync tray service.

Run this to keep syncing even when the ERP window is closed:
    python mobile_tray.py
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.mobile_sync.tray import run_tray

if __name__ == "__main__":
    run_tray()