@echo off
title WarnetPro Client
cd /d "%~dp0"

echo ============================================================
echo   WarnetPro Client
echo   Memeriksa Python...
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Install Python 3.7+ dari https://python.org
    pause
    exit /b 1
)

echo [INFO] Menjalankan client...
echo.

python client_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Client berhenti dengan error.
    pause
)
