$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$service = Join-Path $repo "scripts\lcd_acquisition_service.py"
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "pythonw.exe tidak ditemukan di $pythonw"
}

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Smart Coffee E-Nose Acquisition.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = ('"{0}" --port COM5 --baud 115200' -f $service)
$shortcut.WorkingDirectory = $repo
$shortcut.Description = "Smart Coffee E-Nose passive COM5 acquisition autosave"
$shortcut.Save()

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ieq "pythonw.exe" -and
    $_.CommandLine -like "*lcd_acquisition_service.py*"
}

if (-not $running) {
    Start-Process -FilePath $pythonw -ArgumentList @($service, "--port", "COM5", "--baud", "115200") -WorkingDirectory $repo -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Write-Host "[OK] Autostart terpasang:" $shortcutPath
Write-Host "[OK] Listener target: COM5 @ 115200"
Write-Host "[INFO] Log:" (Join-Path $repo "logs\acquisition_service.log")
Write-Host "[INFO] Status:" (Join-Path $repo "logs\acquisition_service.status.json")
