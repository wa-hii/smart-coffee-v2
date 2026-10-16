@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\check_usb_receiver.py
) else (
  python scripts\check_usb_receiver.py
)
pause
