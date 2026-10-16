@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f=Join-Path ([Environment]::GetFolderPath('Startup')) 'Smart Coffee E-Nose Receiver.lnk'; if(Test-Path -LiteralPath $f){Remove-Item -LiteralPath $f; Write-Host ('Removed: '+$f)}else{Write-Host 'No startup shortcut was installed'}"
echo The running listener, if any, is not stopped. Your CSV files are retained.
pause
