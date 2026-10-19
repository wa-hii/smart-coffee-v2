@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
echo === E-Nose receiver, three devices on COM5 COM6 COM7 ===
echo Read-only COM inspection. This does not open serial ports.
"%PY%" scripts\multi_device_receiver.py --ports COM5 COM6 COM7
if errorlevel 1 goto :fail
echo.
echo Only start when all existing listeners are STOPPED and devices are IDLE.
echo Press Ctrl+C to terminate ONLY after ALL acquisitions have finished.
set /p "CONFIRM=Type START to launch all three receivers: "
if /I not "%CONFIRM%"=="START" goto :done
"%PY%" -u scripts\multi_device_receiver.py --ports COM5 COM6 COM7 --start
:fail
echo Check COM mapping, USB drivers, and existing receiver processes.
:done
pause
