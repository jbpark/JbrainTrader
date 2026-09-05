@echo off
setlocal
chcp 65001 >nul

:: Run this script as a normal user. Only the 32-bit gateway will request elevate if needed.

:: Ensure we are in the correct directory (Elevated sessions often start in System32)
cd /d "%~dp0"

echo ========================================
echo    JBrain System Restart (Admin Mode)
echo ========================================
echo.

echo [1/2] Stopping all processes... (stop.bat)
call stop.bat

echo.
echo [*] Shutdown complete. Restarting system in 3 seconds...
timeout /t 3 >nul

echo.
echo [2/2] Starting system... (run.bat)
call run.bat

echo.
echo [*] All servers restarted successfully.
echo [*] This window will close in 5 seconds.
echo.
timeout /t 5
