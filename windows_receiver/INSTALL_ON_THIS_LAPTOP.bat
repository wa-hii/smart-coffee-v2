@echo off
setlocal
cd /d "%~dp0.."
echo Smart Coffee E-Nose - Windows USB Receiver (one-time setup)
echo Installing inside: %CD%
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 (
  echo ERROR: Install Python 3.10+ for Windows, then run this file again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements_listener.txt
if errorlevel 1 (
  echo ERROR: Python packages could not be installed. Check internet and pip.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\receiver_preflight.py
if errorlevel 1 (
  echo ERROR: Receiver failed the Windows environment preflight.
  echo Run windows_receiver\DIAGNOSE_WINDOWS_10.bat and send the error output.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "windows_receiver\install_autostart.ps1" -AppRoot "%CD%"
if errorlevel 1 (
  echo ERROR: Auto-start could not be installed.
  pause
  exit /b 1
)
echo.
echo Installed. This laptop will listen for a supported E-Nose USB port
echo at next Windows sign-in. If an old receiver is currently running,
echo the installer intentionally does NOT start a competing listener now.
echo Wait for the current Take Data to finish before switching receivers.
echo Raw data directory: %CD%\data\raw
echo Current status: %CD%\logs\acquisition_service.status.json
pause
