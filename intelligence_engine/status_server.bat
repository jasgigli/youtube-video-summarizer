@echo off
setlocal
echo =======================================================
echo   YouTube Summarizer - Background Server Status
echo =======================================================

set PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    set PID=%%a
)

if "%PID%"=="" goto NOT_RUNNING

echo [STATUS] YouTube Summarizer is RUNNING in the background.
echo [PID]    %PID%
echo [PORT]   8000
echo [LOCAL]  http://127.0.0.1:8000/api/health
echo.
echo Querying server health:
powershell -NoProfile -Command "$res = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -ErrorAction Stop; Write-Host ('[HEALTH] Status: ' + $res.status + ' | Version: ' + $res.version)"
echo.
echo Recent logs from data\server.log:
powershell -NoProfile -Command "if (Test-Path 'data\server.log') { Get-Content 'data\server.log' -Tail 10 } else { Write-Host 'No log file yet.' }"
goto END

:NOT_RUNNING
echo [STATUS] YouTube Summarizer is NOT running.
echo [INFO] You can launch it silently with run_silently.vbs or manually with start_server.bat.

:END
echo =======================================================
pause
