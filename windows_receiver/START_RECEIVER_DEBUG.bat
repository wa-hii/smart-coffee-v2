@echo off
setlocal
pushd "%~dp0.." || (echo ERROR: Cannot access receiver folder & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Receiver Python environment missing. Run installer first.
  goto :fail
)
".venv\Scripts\python.exe" scripts\receiver_preflight.py
if errorlevel 1 goto :fail
echo.
echo Starting receiver in foreground. CTRL+C to stop.
echo If a background receiver is already running, this will report its lock.
".venv\Scripts\python.exe" -u scripts\lcd_acquisition_service.py --port auto --baud 115200 --verbose
echo Receiver exit code: %errorlevel%
:fail
popd
pause
