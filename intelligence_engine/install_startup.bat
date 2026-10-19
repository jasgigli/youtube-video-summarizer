@echo off
setlocal
echo =======================================================
echo   Installing YouTube Summarizer to Windows Startup
echo =======================================================
echo.

set SCRIPT_DIR=%~dp0
set VBS_TARGET=%SCRIPT_DIR%run_silently.vbs

powershell -NoProfile -Command ^
    "$wsh = New-Object -ComObject WScript.Shell; " ^
    "$startup = [System.Environment]::GetFolderPath('Startup'); " ^
    "$shortcutPath = Join-Path $startup 'YouTubeSummarizer.lnk'; " ^
    "$shortcut = $wsh.CreateShortcut($shortcutPath); " ^
    "$shortcut.TargetPath = '%VBS_TARGET%'; " ^
    "$shortcut.WorkingDirectory = '%SCRIPT_DIR%'; " ^
    "$shortcut.Description = 'Automated YouTube Video Summarizer (Runs on Boot)'; " ^
    "$shortcut.Save(); " ^
    "Write-Host '[SUCCESS] Created Windows Startup Shortcut at:' $shortcutPath"

echo.
echo [DONE] The summarizer will now automatically run silently in the background
echo        every time your laptop turns on or restarts!
echo =======================================================
pause
