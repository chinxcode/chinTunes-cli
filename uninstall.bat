@echo off
REM ChinTunes 1-Click Complete Uninstaller for Windows

setlocal enabledelayedexpansion

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python uninstall.py
    pause
    exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py uninstall.py
    pause
    exit /b 0
)

echo [!] Python was not found to execute uninstall.py.
pause
