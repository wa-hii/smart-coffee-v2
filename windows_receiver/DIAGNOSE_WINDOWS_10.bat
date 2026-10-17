@echo off
setlocal
pushd "%~dp0.." || (echo ERROR: Cannot access receiver folder & pause & exit /b 1)
echo ================================================
echo Smart Coffee E-Nose - Windows 10 error diagnosis
echo ================================================
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python receiver environment is not installed.
  echo Please run windows_receiver\INSTALL_ON_THIS_LAPTOP.bat first.
  goto :fail
)
".venv\Scripts\python.exe" scripts\receiver_preflight.py
if errorlevel 1 goto :fail
echo.
echo Receiver status, if available:
if exist "logs\acquisition_service.status.json" type "logs\acquisition_service.status.json"
echo.
echo Recent receiver errors, if available:
if exist "logs\acquisition_service.log" powershell -NoProfile -Command "Get-Content -LiteralPath 'logs\acquisition_service.log' -Tail 25"
echo.
echo Diagnostic passed. To see live errors use START_RECEIVER_DEBUG.bat
popd
pause
exit /b 0
:fail
echo.
echo Please copy or screenshot the ERROR message above.
popd
pause
exit /b 1
