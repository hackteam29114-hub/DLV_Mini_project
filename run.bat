@echo off
REM ---------------------------------------------------------------------
REM run.bat - one-command startup for the Vehicle Detection & Counting App
REM Always uses the venv's own Python so pip and uvicorn never mismatch.
REM ---------------------------------------------------------------------

cd /d "%~dp0"

REM Recreate the venv if missing or broken (e.g. project folder was moved/renamed)
IF NOT EXIST venv\Scripts\python.exe (
    echo Creating virtual environment...
    IF EXIST venv rmdir /s /q venv
    python -m venv venv
)

echo Installing/checking dependencies...
venv\Scripts\python.exe -m pip install -r backend\requirements.txt

echo.
echo Starting server at http://127.0.0.1:8000
echo Press CTRL+C to stop.
echo.

venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
