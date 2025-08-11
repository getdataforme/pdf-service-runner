@echo off
echo Starting PDF Extraction Service...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "outputs" mkdir outputs
if not exist "pdfs" mkdir pdfs
if not exist "patterns" mkdir patterns

echo.
echo Starting service on http://localhost:8000
echo Press Ctrl+C to stop the service
echo.

REM Start the service
python start_service.py

pause
