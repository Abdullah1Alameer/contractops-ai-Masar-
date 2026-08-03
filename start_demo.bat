@echo off
title ContractOps AI - Demo Launcher
cd /d "%~dp0"
rem ensure node/npm are reachable even if PATH is stale
set "PATH=%PATH%;C:\Program Files\nodejs;%APPDATA%\npm"
echo ============================================
echo   ContractOps AI - Demo Launcher
echo ============================================
echo.
echo [1/3] Starting backend (port 8000)...
start "ContractOps Backend" /min cmd /c "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
echo [2/3] Starting frontend (port 3000)...
start "ContractOps Frontend" /min cmd /c "cd frontend && npm run dev"
echo [3/3] Waiting for startup, then opening the browser...
timeout /t 15 /nobreak >nul
start http://localhost:3000
echo.
echo Site is up: http://localhost:3000
echo To stop everything: close the two minimized windows in the taskbar.
echo.
pause
