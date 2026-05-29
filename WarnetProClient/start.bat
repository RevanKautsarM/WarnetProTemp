@echo off
title WarnetPro Client v2.0
cd /d "%~dp0"

echo ============================================================
echo   WarnetPro Client v2.0
echo   Memeriksa dependensi Python...
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan. Install Python 3.7+ dari python.org
    pause
    exit /b 1
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Menginstall dependensi...
    python -m pip install -r requirements.txt
    echo.
)

echo [INFO] Menjalankan WarnetPro Client...
echo.
python warnetpro_client_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client berhenti dengan error.
    pause
)
