@echo off
cd /d "d:\Engineering_Projects\02_tools\youtube_video-summarize_automation"

:: Verify if YouTube Summarizer is already running on port 8000
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] YouTube Summarizer is already running on port 8000.
    exit /b 0
)

:: Ensure data directory exists
if not exist "data" mkdir "data"

:: Launch headless server with output redirected to data\server.log
"C:\Python314\python.exe" run.py --host 0.0.0.0 --port 8000 >> "data\server.log" 2>&1
