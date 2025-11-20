@echo off
REM Unified Frontend Startup Script
REM Starts both backend API and Next.js frontend
REM Access everything via http://localhost:3000

REM Ensure this script runs from its own directory
pushd "%~dp0"

echo ========================================
echo   MUTUAL FUND TRACKER - Startup
echo   Unified Frontend: http://localhost:3000
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created successfully.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are already installed
echo Checking Python dependencies...
python -c "import flask, pandas, requests, redis, celery, aiohttp" >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo Dependencies installed successfully.
) else (
    echo Python dependencies already installed.
)

REM Check if Node.js dependencies are installed
echo Checking Node.js dependencies...
if not exist "v0-mf-return-tracker-frontend\node_modules" (
    echo Installing Node.js dependencies...
    cd v0-mf-return-tracker-frontend
    call npm install
    cd ..
    echo Node.js dependencies installed successfully.
) else (
    echo Node.js dependencies already installed.
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set environment variables
set FLASK_ENV=development
set LOG_LEVEL=INFO

REM Start backend API in background
echo.
echo Starting backend API server...
start "MF Backend API" /MIN cmd /k "call venv\Scripts\activate.bat && set FLASK_ENV=development && python app.py"

REM Wait for backend to initialize
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Start Next.js frontend
echo Starting Next.js frontend...
start "MF Frontend" cmd /k "cd v0-mf-return-tracker-frontend && npm run dev"

REM Wait for frontend to start
timeout /t 5 /nobreak >nul

REM Open browser to unified frontend
echo Opening browser to unified frontend...
start "" "http://localhost:3000"

echo.
echo ========================================
echo   Application Started Successfully!
echo ========================================
echo.
echo   Access the application at:
echo   http://localhost:3000
echo.
echo   Backend API: http://localhost:5000 (API only)
echo   Frontend:    http://localhost:3000 (Main UI)
echo.
echo   Press Ctrl+C in the frontend window to stop.
echo.

REM Return to original directory
popd

pause 