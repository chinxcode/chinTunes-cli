@echo off
REM ChinTunes 1-Click Setup for Windows
python install.py
if %ERRORLEVEL% NEQ 0 (
    py install.py
)
pause
