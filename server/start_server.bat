@echo off
title WarnetPro Operator Dashboard (Lokal)
cd /d "%~dp0"

echo ============================================================
echo   WarnetPro Operator Dashboard - Mode Lokal Mandiri
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

echo [INFO] Menjalankan dashboard operator lokal...
echo.

python operator_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Dashboard berhenti dengan error.
    pause
)
