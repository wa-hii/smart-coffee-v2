# Read-only Windows inspection. Does NOT open, close or reset any serial port.
$ErrorActionPreference = 'Stop'
Write-Host '=== Smart Coffee E-Nose: receiver process / save location audit ==='
$processes = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^pythonw?\.exe$' -and
    $_.CommandLine -like '*lcd_acquisition_service.py*'
})
$receiverRoots = @()
if ($processes.Count -eq 0) {
    Write-Host 'No running receiver found. Start ONE receiver before Take Data.'
} else {
    Write-Host ('Active receiver processes: ' + $processes.Count)
}
foreach ($p in $processes) {
    Write-Host ('--- PID ' + $p.ProcessId + ' ---')
    $m = [regex]::Match($p.CommandLine, '"?([^"\s]+(?:\\[^"\s]+)*?)\\scripts\\lcd_acquisition_service\.py')
    if (-not $m.Success) {
        # Paths with spaces are normally quoted; report raw argv for diagnosis.
    Write-Host ('Command: ' + $p.CommandLine)
    continue
    }
    $root = $m.Groups[1].Value
    $receiverRoots += $root
    $statusFile = Join-Path $root 'logs\acquisition_service.status.json'
    Write-Host ('Receiver root: ' + $root)
    Write-Host ('Expected CSV directory: ' + (Join-Path $root 'data\raw'))
    if (Test-Path -LiteralPath $statusFile) {
        try {
            $state = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
            Write-Host ('State: ' + $state.state + '; port: ' + $state.port + '; status PID: ' + $state.pid)
        } catch { Write-Warning ('Cannot read status: ' + $_.Exception.Message) }
    }
}
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Smart Coffee E-Nose Receiver.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
    Write-Host ('Startup target: ' + $link.TargetPath)
    Write-Host ('Startup arguments: ' + $link.Arguments)
} else {
    Write-Host 'Startup shortcut not installed.'
}
$uniqueRoots = @($receiverRoots | Sort-Object -Unique)
Write-Host ('Distinct installation roots: ' + $uniqueRoots.Count +
            ' (one receiver can use launcher + interpreter processes)')
if ($uniqueRoots.Count -gt 1) {
    Write-Warning 'Multiple listeners detected: they may compete for COM and save into DIFFERENT data/raw folders.'
    Write-Host 'Do NOT stop any active session. Reconcile processes only when hardware is confirmed IDLE.'
}
