@echo off
REM ChinTunes 1-Click Setup for Windows
REM Analyzes Python and prompts to install if missing.

setlocal enabledelayedexpansion

echo.
echo ==============================================
echo   ChinTunes Pre-Flight System Check (Windows)
echo ==============================================
echo.

REM 1. Check Python
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py"
    goto :PYTHON_FOUND
)

echo [!] Python was not found on your system.
set "INSTALL_PY=Y"
set /p INSTALL_PY="Would you like to auto-install Python now using Windows winget? [Y/n]: "
if /i "%INSTALL_PY%"=="Y" (
    where winget >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo [*] Installing Python 3 via winget...
        winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        set "PY_CMD=python"
    ) else (
        echo [X] Winget not found. Opening python.org download page...
        start https://www.python.org/downloads/
        echo Please complete Python installation and re-run install.bat.
        pause
        exit /b 1
    )
) else (
    echo Python is required to run ChinTunes. Exiting.
    pause
    exit /b 1
)

:PYTHON_FOUND
echo [+] Python detected!
%PY_CMD% install.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Installation encountered an issue.
)

pause
