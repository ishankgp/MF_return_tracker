@echo off
REM Quick start - Unified Frontend Approach
REM All access via Next.js frontend at http://localhost:3000
REM Flask backend runs as API-only on http://localhost:5000

REM Ensure this script runs from its own directory
pushd "%~dp0"

echo ========================================
echo   MUTUAL FUND TRACKER - Quick Start
echo   Unified Frontend: http://localhost:3000
echo ========================================
echo.

REM Start backend (API only) in new window
echo Starting backend API server...
start "MF Backend API" cmd /k "call venv\Scripts\activate.bat && python app.py"

REM Wait for backend to initialize
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Start Next.js frontend in new window
echo Starting Next.js frontend...
start "MF Frontend" cmd /k "cd v0-mf-return-tracker-frontend && npm run dev"

REM Wait for frontend to start
timeout /t 5 /nobreak >nul

REM Open browser to unified frontend
echo Opening browser...
start "" "http://localhost:3000"

echo.
echo ========================================
echo   Access the application at:
echo   http://localhost:3000
echo ========================================
echo.
echo Backend API: http://localhost:5000 (API only)
echo Frontend:    http://localhost:3000 (Main UI)
echo.
echo Close this window when done. The apps will continue running.

REM Return to original directory
popd
pause
