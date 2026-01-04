@echo off
REM Mutual Fund Returns Tracker - Startup Script
REM Flask-only application

REM Ensure this script runs from its own directory
pushd "%~dp0"

echo ========================================
echo   MUTUAL FUND TRACKER - Starting
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
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are already installed
echo Checking Python dependencies...
python -c "import flask, pandas, requests" >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
) else (
    echo Python dependencies already installed.
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set environment variables
set FLASK_ENV=development
set LOG_LEVEL=INFO

echo.
echo Starting Flask server...
echo.

REM Start Flask server
start "MF Tracker - Flask Server" cmd /k "call venv\Scripts\activate.bat && python app.py"

REM Wait for server to initialize
timeout /t 3 /nobreak >nul

REM Open browser
echo Opening browser...
start "" "http://localhost:5000"

echo.
echo ========================================
echo   Application Started Successfully!
echo ========================================
echo.
echo   Access the application at:
echo   http://localhost:5000
echo.
echo   Press any key to close this window.
echo   The Flask server will continue running.
echo.

REM Return to original directory
popd

pause
