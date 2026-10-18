# Configure ONE auto-detect Startup listener for the project checkout.
# This changes only Startup shortcuts. It does not stop processes/open COM.
param(
    [Parameter(Mandatory=$true)][string]$AppRoot,
    [Parameter(Mandatory=$true)][string]$PythonwPath,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $AppRoot).Path.TrimEnd('\')
$script = Join-Path $root 'scripts\lcd_acquisition_service.py'
$exe = (Resolve-Path -LiteralPath $PythonwPath).Path
if (-not (Test-Path -LiteralPath $script)) { throw 'Cannot find receiver source.' }
$startup = [Environment]::GetFolderPath('Startup')
$old = Join-Path $startup 'Smart Coffee E-Nose Acquisition.lnk'
$new = Join-Path $startup 'Smart Coffee E-Nose Receiver.lnk'
$backupDir = Join-Path $root 'results\startup_receiver_backup_20261018'
$args = '"' + $script + '" --port auto --baud 115200'
Write-Host ('Target: ' + $exe)
Write-Host ('Args: ' + $args)
Write-Host ('Working directory / CSV root: ' + $root)
Write-Host ('Legacy COM5 shortcut: ' + $old)
Write-Host ('Existing receiver shortcut: ' + $new)
Write-Host ('Backup directory: ' + $backupDir)
if (-not $Apply) {
    Write-Host 'DRY RUN ONLY. Pass -Apply after reviewing the shortcuts.'
    exit 0
}
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
if (Test-Path -LiteralPath $old) {
    Copy-Item -LiteralPath $old -Destination (Join-Path $backupDir ($stamp + '_Acquisition.lnk')) -ErrorAction Stop
}
if (Test-Path -LiteralPath $new) {
    Copy-Item -LiteralPath $new -Destination (Join-Path $backupDir ($stamp + '_Receiver.lnk')) -ErrorAction Stop
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($new)
$shortcut.TargetPath = $exe
$shortcut.Arguments = $args
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Smart Coffee E-Nose single automatic USB listener, project data/raw'
$shortcut.Save()
if (Test-Path -LiteralPath $old) {
    Remove-Item -LiteralPath $old -ErrorAction Stop
}
Write-Host 'Startup repaired; legacy shortcuts backed up. No existing process was stopped.'
Write-Host 'Restart/close legacy listeners ONLY after Take Data is finished and hardware is IDLE.'
