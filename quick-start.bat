@echo off
REM Quick start - assumes everything is already installed

REM Ensure this script runs from its own directory
pushd "%~dp0"

echo Starting Mutual Fund Tracker (Quick Mode)...
echo.

REM Start backend in new window
start "MF Backend" cmd /k "call venv\Scripts\activate.bat && python app.py"

REM Wait 2 seconds for backend to initialize
timeout /t 2 /nobreak >nul

REM Start frontend in new window
start "MF Frontend" cmd /k "cd v0-mf-return-tracker-frontend && npm run dev"

echo.
echo Backend starting at: http://127.0.0.1:5000
echo Frontend starting at: http://localhost:3000
echo.
echo Close this window when done. The apps will continue running.

REM Return to original directory
popd
pause
