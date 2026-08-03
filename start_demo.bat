@echo off
chcp 65001 >nul
title ContractOps AI - Demo Launcher
echo ============================================
echo   ContractOps AI - تشغيل العرض
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] تشغيل الخادم الخلفي (backend)...
start "ContractOps Backend" /min cmd /c "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo [2/3] تشغيل الواجهة (frontend)...
start "ContractOps Frontend" /min cmd /c "cd frontend && npm run dev"

echo [3/3] انتظار الإقلاع ثم فتح المتصفح...
timeout /t 12 /nobreak >nul
start http://localhost:3000

echo.
echo ✅ الموقع اشتغل: http://localhost:3000
echo    لإيقاف كل شيء: أغلق النافذتين المصغرتين من شريط المهام
echo.
pause
