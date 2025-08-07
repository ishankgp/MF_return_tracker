@echo off
echo Starting Mutual Fund Returns Tracker in Production Mode...
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
echo Checking dependencies...
python -c "import flask, pandas, requests, redis, celery, aiohttp, waitress" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo Dependencies installed successfully.
) else (
    echo Dependencies already installed.
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set environment variables for production
set FLASK_ENV=production
set LOG_LEVEL=WARNING
set DEBUG=False

REM Start the application with Waitress (Windows-compatible)
echo.
echo Starting the application with Waitress...
echo The app will be available at http://127.0.0.1:5000
echo Press Ctrl+C to stop the server
echo.

python production_server.py

pause 