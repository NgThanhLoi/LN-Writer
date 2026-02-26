@echo off
chcp 65001 > nul
title LN-Writer

set ROOT=%~dp0
set FRONTEND=%ROOT%frontend

echo [1/2] Khoi dong API (port 8000)...
start "LN-Writer API" cmd /k "cd /d %ROOT% && uvicorn api:app --reload --port 8000"

timeout /t 2 /nobreak > nul

echo [2/2] Khoi dong Frontend (port 3000)...
start "LN-Writer Frontend" cmd /k "cd /d %FRONTEND% && npm run dev"

timeout /t 3 /nobreak > nul

echo.
echo  API      : http://localhost:8000
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8000/docs
echo.
echo Dang mo trinh duyet...
start http://localhost:3000

exit
