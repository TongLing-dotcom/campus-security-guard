@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] python not found in PATH.
    echo Please install Python or add it to PATH, then try again.
    echo.
    pause
    exit /b 1
)

python menu.py

echo.
pause
