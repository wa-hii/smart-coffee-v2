$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Smart Coffee E-Nose Acquisition.lnk"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ieq "pythonw.exe" -and
    $_.CommandLine -like "*lcd_acquisition_service.py*"
}

foreach ($proc in $running) {
    Stop-Process -Id $proc.ProcessId -Force
}

if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
}

Write-Host "[OK] Listener background dihentikan dan autostart dilepas."
