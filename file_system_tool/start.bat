@echo off
echo Starting File System Recovery Tool...

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo Starting backend server...
start cmd /k python -m uvicorn backend.src.api.main:app --reload --port 8000

timeout /t 3

echo Starting frontend server...
cd frontend
start cmd /k npm run dev

echo Application started!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
