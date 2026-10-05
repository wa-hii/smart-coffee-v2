$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$statusPath = Join-Path $repo "logs\acquisition_service.status.json"
$logPath = Join-Path $repo "logs\acquisition_service.log"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ieq "pythonw.exe" -and
    $_.CommandLine -like "*lcd_acquisition_service.py*"
}

if ($running) {
    Write-Host "[RUNNING] lcd_acquisition_service.py"
    $running | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
} else {
    Write-Host "[STOPPED] lcd_acquisition_service.py"
}

if (Test-Path $statusPath) {
    Write-Host "--- status ---"
    Get-Content $statusPath
}

if (Test-Path $logPath) {
    Write-Host "--- last log lines ---"
    Get-Content $logPath -Tail 12
}
