param([Parameter(Mandatory=$true)][string]$AppRoot)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $AppRoot).Path.TrimEnd('\')
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
$script = Join-Path $root 'scripts\lcd_acquisition_service.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $script)) {
    throw 'Python virtual environment / listener not installed'
}
New-Item -ItemType Directory -Force -Path (Join-Path $root 'data\raw') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $root 'data\baseline') | Out-Null
$startup = [Environment]::GetFolderPath('Startup')
if ([string]::IsNullOrWhiteSpace($startup)) { throw 'Windows Startup folder not available' }
$linkPath = Join-Path $startup 'Smart Coffee E-Nose Receiver.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = $python
$shortcut.Arguments = ('"{0}" --port auto --baud 115200' -f $script)
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Smart Coffee E-Nose USB-to-CSV automatic receiver'
$shortcut.Save()
Write-Host ('Startup shortcut: ' + $linkPath)
# Existing listener may already hold a process lock. Never terminate it here.
# One duplicate attempt exits immediately without touching the active session.
Start-Process -FilePath $python -ArgumentList @('"' + $script + '"', '--port', 'auto', '--baud', '115200') -WorkingDirectory $root
Write-Host 'Listener launch requested; inspect logs/acquisition_service.status.json for connected/waiting state.'
