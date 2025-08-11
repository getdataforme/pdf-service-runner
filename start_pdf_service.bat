@echo off
REM Windows batch file to start the unified PDF extraction and viewing service

echo ===============================================
echo    PDF EXTRACTION ^& VIEWING SERVICE
echo ===============================================
echo.

cd /d "%~dp0"

echo Starting unified PDF service...
echo.

python start_pdf_service.py

pause
