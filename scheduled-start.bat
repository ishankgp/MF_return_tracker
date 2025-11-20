@echo off
REM Production startup script for Task Scheduler - Unified Frontend Approach
REM All access via Next.js frontend at http://localhost:3000
REM Flask backend runs as API-only on http://localhost:5000

REM Ensure this script runs from its own directory
pushd "%~dp0"

echo ========================================
echo   MUTUAL FUND TRACKER - Daily Update
echo   Time: %time%  Date: %date%
echo ========================================
echo.

REM Set production environment
set FLASK_ENV=production
set LOG_LEVEL=INFO

REM Kill any existing instances to prevent duplicates
echo Cleaning up old instances...
taskkill /F /FI "WindowTitle eq MF Backend*" >nul 2>&1
taskkill /F /FI "WindowTitle eq MF Frontend*" >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start backend (keeps running in minimized window)
echo Starting backend server...
start "MF Backend" /MIN cmd /k "call venv\Scripts\activate.bat && set FLASK_ENV=production && python app.py"

REM Wait for backend to initialize
timeout /t 5 /nobreak >nul

REM Start frontend (keeps running in minimized window)
echo Building frontend for production...
cd v0-mf-return-tracker-frontend
set NODE_ENV=production
call npm run build
if errorlevel 1 (
    echo Build failed, but continuing with development server...
    cd ..
    start "MF Frontend" /MIN cmd /k "cd v0-mf-return-tracker-frontend && set NODE_ENV=production && npm run dev"
) else (
    cd ..
    echo Starting frontend server...
    start "MF Frontend" /MIN cmd /k "cd v0-mf-return-tracker-frontend && set NODE_ENV=production && npm start"
)

REM Wait for servers to fully start
timeout /t 10 /nobreak >nul

REM Open browser to unified frontend (single entry point)
echo Opening browser to unified frontend...
start "" "http://localhost:3000"

REM Return to original directory  
popd

