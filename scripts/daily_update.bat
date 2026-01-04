@echo off
REM Mutual Fund Returns Tracker - Daily Update Script
REM Designed for Windows Task Scheduler

pushd "%~dp0"
cd ..

echo %DATE% %TIME% - Starting update... >> logs\scheduler_bat.log

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Error: venv not found >> logs\scheduler_bat.log
    exit /b 1
)

REM Run the refresh script
python scripts\refresh_data.py
if errorlevel 1 (
    echo %DATE% %TIME% - Update Failed >> logs\scheduler_bat.log
) else (
    echo %DATE% %TIME% - Update Successful >> logs\scheduler_bat.log
)

popd
exit /b 0
