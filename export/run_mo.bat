@echo off
setlocal
pushd "%~dp0"

set PYTHON_BIN=C:\ProgramData\anaconda3\python.exe
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%CD%\..;%PYTHONPATH%

set STOCK_SERVER=%1
if "%STOCK_SERVER%"=="" set STOCK_SERVER=hankook

echo Starting Mock Trading for %STOCK_SERVER%...

if "%STOCK_SERVER%"=="kiwoom" (
    echo Launching Kiwoom Gateway...
    start "" /d "%~dp0.." run_kiwoom_admin.bat
    timeout /t 5 > nul
)

"%PYTHON_BIN%" martingale_mo.py --server %STOCK_SERVER%
pause
popd
endlocal
