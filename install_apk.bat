@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
echo ============================================
echo   APK 휴대폰 설치 (ADB)
echo ============================================
echo.

set APK_PATH=%~dp0trading_app\build\app\outputs\flutter-apk\app-release.apk

:: APK 파일 존재 확인
if not exist "%APK_PATH%" (
    echo [오류] APK 파일이 없습니다.
    echo 먼저 build_apk.bat 를 실행하여 APK를 빌드해주세요.
    echo.
    echo 예상 경로: %APK_PATH%
    pause
    exit /b 1
)

echo APK 파일 경로: %APK_PATH%
echo.

:: ADB 명령어 확인 및 경로 설정
where adb >nul 2>nul
if %errorlevel% neq 0 (
    set ADB_EXE="%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
    if not exist !ADB_EXE! (
        echo [오류] adb 명령어를 찾을 수 없고, 기본 SDK 경로에도 없습니다.
        echo 환경 변수 PATH에 adb 경로를 추가해 주세요.
        pause
        exit /b 1
    )
) else (
    set ADB_EXE=adb
)

:: 연결된 기기 확인
echo 연결된 기기 목록:
%ADB_EXE% devices
echo.

:: 기기 연결 여부 확인 및 타겟 설정
set TARGET_FLAG=
set DEVICE_FOUND=
set PHYSICAL_DEVICE_FOUND=
set TARGET_DEVICE=

for /f "skip=1 tokens=1,2" %%d in ('!ADB_EXE! devices') do (
    if "%%e"=="device" (
        set DEVICE_FOUND=true
        rem 에뮬레이터가 아닌 실제 기기(Serial Number) 타겟팅
        echo %%d | findstr /i "emulator" > nul
        if errorlevel 1 (
            set PHYSICAL_DEVICE_FOUND=true
            set TARGET_DEVICE=%%d
        )
    )
)

if not defined DEVICE_FOUND (
    echo [오류] 연결된 기기가 없습니다.
    echo.
    echo 확인사항:
    echo   1. USB 케이블로 휴대폰 연결
    echo   2. 휴대폰에서 "USB 디버깅" 허용
    echo   3. "이 컴퓨터를 항상 신뢰" 선택
    pause
    exit /b 1
)

rem 여러 기기가 있을 때 실제 기기를 우선 타겟팅
if defined PHYSICAL_DEVICE_FOUND (
    set TARGET_FLAG=-s !TARGET_DEVICE!
    echo 타겟 기기: !TARGET_DEVICE!
) else (
    set TARGET_FLAG=
)

echo APK 설치 중...
!ADB_EXE! !TARGET_FLAG! install -r "%APK_PATH%"



if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   설치 완료!
    echo   휴대폰에서 'trading_app' 앱을 실행하세요.
    echo ============================================
) else (
    echo.
    echo [오류] 설치 실패
    echo 휴대폰 화면에서 설치 허용 팝업을 확인해주세요.
)

echo.
pause
