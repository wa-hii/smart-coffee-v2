param(
    [Parameter(Mandatory=$true)][string]$AppRoot,
    [string]$UsbSerial = '',
    [string]$PythonwPath = '',
    [switch]$SkipLaunch
)
$ErrorActionPreference = 'Stop'
if ($UsbSerial -ne '' -and $UsbSerial -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'Invalid USB serial ID for receiver shortcut'
}
$root = (Resolve-Path -LiteralPath $AppRoot).Path.TrimEnd('\')
$python = if ($PythonwPath -ne '') {
    (Resolve-Path -LiteralPath $PythonwPath).Path
} else {
    Join-Path $root '.venv\Scripts\pythonw.exe'
}
$script = Join-Path $root 'scripts\lcd_acquisition_service.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $script)) {
    throw 'Python virtual environment / listener not installed'
}
New-Item -ItemType Directory -Force -Path (Join-Path $root 'data\raw') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root 'data\baseline') | Out-Null
$startup = [Environment]::GetFolderPath('Startup')
if ([string]::IsNullOrWhiteSpace($startup)) { throw 'Windows Startup folder not available' }
$linkPath = Join-Path $startup 'Smart Coffee E-Nose Receiver.lnk'
$shortcutArgs = ('"{0}" --port auto --baud 115200' -f $script)
if ($UsbSerial -ne '') {
    $shortcutArgs += ' --usb-serial ' + $UsbSerial
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = $python
$shortcut.Arguments = $shortcutArgs
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Smart Coffee E-Nose USB-to-CSV automatic receiver'
$shortcut.Save()
Write-Host ('Startup shortcut: ' + $linkPath)
# Useful while the bootloader of the target PCB is being diagnosed:
# configure the shortcut without opening COM or auto-starting the receiver.
if ($SkipLaunch) {
    Write-Host 'Shortcut updated only; receiver not launched.'
    return
}
# Do not start another copy while an older receiver from another extracted
# directory is active. Older builds do not share our host-wide mutex.
$existing = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^pythonw?\.exe$' -and
    $_.CommandLine -like '*lcd_acquisition_service.py*'
})
if ($existing.Count -gt 0) {
    Write-Warning ('Found ' + $existing.Count + ' receiver-related Python processes. ' +
        'Startup shortcut was updated, but no new receiver was launched. ' +
        'Do not stop any process until the current Take Data is finished and the device is IDLE.')
    return
}
$launchArgs = @('"' + $script + '"', '--port', 'auto', '--baud', '115200')
if ($UsbSerial -ne '') { $launchArgs += @('--usb-serial', $UsbSerial) }
Start-Process -FilePath $python -ArgumentList $launchArgs -WorkingDirectory $root
Write-Host 'Listener launch requested; inspect logs/acquisition_service.status.json for connected/waiting state.'
