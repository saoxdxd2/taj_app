@echo off
echo =========================================
echo TAJ FROID ERP - Build Pipeline
echo =========================================

echo.
echo Installing build requirements...
python -m pip install -r requirements-dev.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install requirements.
    exit /b %ERRORLEVEL%
)

echo.
echo Executing Python Build Script...
python build.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build script failed.
    exit /b %ERRORLEVEL%
)

echo.
echo Build Pipeline completed successfully.
echo Output is available in the dist\ directory.
pause
