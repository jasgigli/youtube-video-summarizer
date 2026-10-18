@echo off
setlocal
echo =======================================================
echo   Removing YouTube Summarizer from Windows Startup
echo =======================================================
echo.

powershell -NoProfile -Command ^
    "$startup = [System.Environment]::GetFolderPath('Startup'); " ^
    "$shortcutPath = Join-Path $startup 'YouTubeSummarizer.lnk'; " ^
    "if (Test-Path $shortcutPath) { Remove-Item $shortcutPath -Force; Write-Host '[SUCCESS] Removed shortcut from Windows Startup.' } else { Write-Host '[INFO] No startup shortcut was found.' }"

echo.
echo =======================================================
pause
