@echo off
setlocal
cd /d "%~dp0.."
echo Smart Coffee E-Nose: install dependencies for THREE simultaneous devices.
echo This installation does NOT enable single-device autostart or open COM.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements_listener.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" scripts\receiver_preflight.py
if errorlevel 1 goto :fail
echo.
echo Installation PASS. No port was opened or startup changed.
echo To start three devices: windows_receiver\START_THREE_ENOSE_COM5_COM6_COM7.bat
pause
exit /b 0
:fail
echo ERROR during receiver install. Do NOT start Take Data before resolving.
pause
exit /b 1
