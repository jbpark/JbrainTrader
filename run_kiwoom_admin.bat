@echo off
chcp 65001 > nul

:: ============================================================
::  [Kiwoom Gateway 관리자 권한 실행기]
::  자동 로그인(WM_SETTEXT, pyautogui)에는 관리자 권한이 필요합니다.
::  UAC 확인 후 자동으로 관리자 권한으로 재실행합니다.
:: ============================================================

>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [Kiwoom Gateway] 관리자 권한 필요 - UAC 승인 후 재실행됩니다...
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin_kiwoom.vbs"
    echo UAC.ShellExecute "cmd.exe", "/k cd /d ""%~dp0"" && ""%~s0""", "", "runas", 1 >> "%temp%\getadmin_kiwoom.vbs"
    "%temp%\getadmin_kiwoom.vbs"
    exit /B
)

:: ── 관리자 권한 획득 완료 ──
if exist "%temp%\getadmin_kiwoom.vbs" ( del "%temp%\getadmin_kiwoom.vbs" )
pushd "%~dp0"
setlocal

set PYTHON_32="C:\Program Files (x86)\Python311-32\python.exe"

echo ==================================================
echo   Kiwoom Gateway (32-bit) - 관리자 모드 실행
echo ==================================================
echo.

echo [*] 32비트 필수 패키지 설치 확인...
%PYTHON_32% -m pip install flask flask-cors pywin32 PyQt5 pandas==2.0.3 numpy pymysql openpyxl pyzmq backtrader cryptography python-dotenv pywinauto pyperclip pyautogui > nul 2>&1

echo [*] PYTHONPATH = %CD%
set PYTHONPATH=%CD%
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo [*] Kiwoom Gateway (32-bit) 시작 (관리자 권한)...
echo [*] Vue 프론트엔드에서 '연결 설정'을 클릭하면 자동 로그인이 시작됩니다.
echo.

%PYTHON_32% -m kiwoom.api_server

echo.
echo [!] Kiwoom Gateway 종료됨.
@REM pause

exit