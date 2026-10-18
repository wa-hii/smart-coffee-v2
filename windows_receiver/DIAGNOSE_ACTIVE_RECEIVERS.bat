@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0DIAGNOSE_ACTIVE_RECEIVERS.ps1"
echo.
echo Read-only report. No serial port was opened or stopped.
pause
