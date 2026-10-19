@echo off
setlocal
pushd "%~dp0.." || exit /b 1
echo Three-instrument read-only incident report (no COM opened).
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\diagnose_three_receivers.py
) else (
  python scripts\diagnose_three_receivers.py
)
popd
pause
