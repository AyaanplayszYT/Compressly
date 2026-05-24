@echo off
setlocal enabledelayedexpansion
title Compressly Setup

echo.
echo  ============================================
echo   Compressly Setup — by Mistix
echo  ============================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python not found.
    echo.
    echo  Compressly requires Python 3.10 or newer.
    echo  Opening the Python download page...
    echo.
    start https://www.python.org/downloads/
    echo  After installing Python, run this setup again.
    echo  Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% found.

:: ── Check pip ─────────────────────────────────────────────────────────────
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] pip not found. Installing...
    python -m ensurepip --upgrade
)
echo  [OK] pip ready.

:: ── Create virtual environment ────────────────────────────────────────────
if not exist ".venv" (
    echo.
    echo  Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [!] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created.
) else (
    echo  [OK] Virtual environment already exists.
)

:: ── Install dependencies ──────────────────────────────────────────────────
echo.
echo  Installing dependencies (this may take a few minutes on first run)...
echo.

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

if %errorlevel% neq 0 (
    echo.
    echo  [!] Dependency installation failed.
    echo  Try running this script as Administrator, or check your internet connection.
    pause
    exit /b 1
)

echo.
echo  [OK] All dependencies installed.

:: ── Launch the app ────────────────────────────────────────────────────────
echo.
echo  Launching Compressly...
echo.
start "" python main.py

echo  Compressly is running. You can close this window.
timeout /t 3 >nul
exit /b 0
