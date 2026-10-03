@echo off
TITLE PCD Compiler Optimization Advisor - Production Launcher
COLOR 0B

echo =======================================================================
echo     ML-Powered Compiler Optimization Advisor (Production Mode)
echo =======================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [1/2] Building React production bundle...
cd /d "%~dp0frontend_new"
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

cd /d "%~dp0backend"

echo [2/2] Launching Flask Unified Server...
echo App available at: http://127.0.0.1:5000/
echo.

timeout /t 2 >nul
start http://127.0.0.1:5000/

python app.py

pause
