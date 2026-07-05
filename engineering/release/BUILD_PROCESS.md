# Build Process Documentation

**Version:** 1.0
**Status:** IMMUTABLE

This document governs the build process for TAJ FROID ERP Release Candidate 1 (RC1) and beyond.

## 1. Overview
The build process compiles the Python application into a standalone Windows Executable using PyInstaller.

## 2. Prerequisites
- Python 3.14+
- `pip install -r requirements.txt`
- `pip install pyinstaller`

## 3. Build Command
To produce a clean, reproducible build:
1. Open a command prompt in the repository root.
2. Run `build.bat`.

## 4. Pipeline Execution
The pipeline executes the following stages:
1. **Clean**: Deletes any existing `build/` and `dist/` directories to prevent artifacts from leaking into the new build.
2. **Spec Generation**: Dynamically creates `taj_froid.spec` tailored to the current environment and configuration.
3. **Compile**: Invokes `pyinstaller` using the generated spec file.
   - Bundles `alembic.ini` and `migrations/`.
   - Forces hidden imports for dynamic modules (SQLAlchemy, Alembic, Loguru, etc.).
   - Generates a non-console (GUI) executable.
4. **Output**: The compiled application will be located in `dist/TAJ_FROID_ERP/`.

## 5. Verification
After the build completes, always perform a dry run of the executable located at `dist/TAJ_FROID_ERP/TAJ_FROID_ERP.exe` to verify:
- Alembic database migration succeeds dynamically on a cold start.
- PySide6 GUI launches without missing DLL errors.
- Logs correctly stream to `%LOCALAPPDATA%\TAJ_FROID\logs`.
