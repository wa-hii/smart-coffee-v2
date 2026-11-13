$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$service = Join-Path $repo "scripts\lcd_acquisition_service.py"
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "pythonw.exe tidak ditemukan di $pythonw"
}

$startup = [Environment]::GetFolderPath("Startup")
# Gunakan shortcut canonical yang sama dengan Windows receiver; hindari
# membuat dua autorun berbeda yang saling berebut COM11.
$shortcutPath = Join-Path $startup "Smart Coffee E-Nose Receiver.lnk"
# Ikuti identitas USB PCB kedua meski Windows mengganti nomor COM11.
# Jangan gunakan nomor seri FT232R/COM5 yang berasal dari PCB lain.
$ftdiSerial = "A10KNJBLA"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = ('"{0}" --port auto --usb-serial {1} --baud 115200' -f $service, $ftdiSerial)
$shortcut.WorkingDirectory = $repo
$shortcut.Description = "Smart Coffee E-Nose PCB kedua COM11 (FTDI $ftdiSerial) autosave"
$shortcut.Save()

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -ieq "pythonw.exe" -and
    $_.CommandLine -like "*lcd_acquisition_service.py*"
}

if (-not $running) {
    Start-Process -FilePath $pythonw -ArgumentList @($service, "--port", "auto", "--usb-serial", $ftdiSerial, "--baud", "115200") -WorkingDirectory $repo -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Write-Host "[OK] Autostart terpasang:" $shortcutPath
Write-Host "[OK] Listener target: FT232RL $ftdiSerial (sekarang COM11) @ 115200"
Write-Host "[INFO] Log:" (Join-Path $repo "logs\acquisition_service.log")
Write-Host "[INFO] Status:" (Join-Path $repo "logs\acquisition_service.status.json")
