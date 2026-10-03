@echo off
TITLE PCD Compiler Optimization Advisor - Startup Script
COLOR 0A

echo =======================================================================
echo          ML-Powered Compiler Optimization Advisor Launcher
echo =======================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9+ and try again.
    pause
    exit /b 1
)

:: Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js 18+ and try again.
    pause
    exit /b 1
)

echo [1/3] Checking frontend build dependencies...
if not exist "%~dp0frontend_new\node_modules\" (
    echo [INFO] Installing npm packages in frontend_new...
    cd /d "%~dp0frontend_new"
    call npm install
    cd /d "%~dp0"
)

echo [2/3] Starting Flask Backend Server (Port 5000)...
start "Flask Backend (Port 5000)" cmd /k "cd /d "%~dp0backend" && python app.py"

echo [3/3] Starting React Vite Frontend Server (Port 5173)...
start "React Frontend (Port 5173)" cmd /k "cd /d "%~dp0frontend_new" && npm run dev"

echo.
echo =======================================================================
echo  Success! Both servers are starting up in background windows.
echo  - Backend API:  http://127.0.0.1:5000/api/health
echo  - React App:    http://localhost:5173/
echo =======================================================================
echo.

timeout /t 3 >nul
start http://localhost:5173/

exit /b 0
