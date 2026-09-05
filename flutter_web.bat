@echo off
chcp 65001 > nul
echo ============================================
echo   Flutter Web (Chrome) 실행
echo ============================================
echo.

cd /d %~dp0trading_app

:: web 폴더가 없으면 web 지원 추가
if not exist "web" (
    echo [준비] web 폴더가 없습니다. web 지원을 추가합니다...
    call flutter create --platforms=web .
    if %errorlevel% neq 0 (
        echo [오류] web 지원 추가 실패
        pause
        exit /b 1
    )
    echo [완료] web 폴더가 생성되었습니다.
    echo.
) else (
    echo [확인] web 폴더가 존재합니다.
    echo.
)

echo [실행] Flutter Web (Chrome) 디버그 모드 시작 중...
echo        r     = Hot Reload
echo        R     = Hot Restart
echo        q     = 종료
echo.
echo ============================================

call flutter run -d chrome

echo.
pause
