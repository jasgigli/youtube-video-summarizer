@echo off
setlocal enabledelayedexpansion
echo [INFO] Looking for YouTube Summarizer process on port 8000...

set PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    set PID=%%a
)

if "%PID%"=="" (
    echo [INFO] YouTube Summarizer is not currently running.
) else (
    echo [INFO] Found process running with PID %PID%. Terminating...
    taskkill /F /PID %PID%
    if !errorlevel! equ 0 (
        echo [SUCCESS] YouTube Summarizer stopped successfully.
    ) else (
        echo [ERROR] Failed to stop PID %PID%.
    )
)

pause
