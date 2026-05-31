@echo off
title WarnetPro Server (Operator)
cd /d "%~dp0"

echo ============================================================
echo   WarnetPro Server - Operator Dashboard
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

echo [INFO] Menjalankan server...
echo [INFO] Untuk auto-firewall, jalankan sebagai Administrator.
echo.

python operator_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server berhenti dengan error.
    pause
)
