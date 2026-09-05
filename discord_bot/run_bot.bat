@echo off
chcp 65001 > nul
echo ============================================
echo   Discord Trading Bot 실행
echo ============================================
echo.

cd /d %~dp0

:: .env 파일 확인
if not exist ".env" (
    echo [경고] .env 파일이 없습니다.
    echo        .env.example 을 참고하여 .env 파일을 생성해주세요.
    echo.
    pause
    exit /b 1
)

:: 패키지 설치 확인
echo [1/2] 필요 패키지 설치 확인 중...
pip install discord.py aiohttp python-dotenv --quiet
if %errorlevel% neq 0 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

echo [2/2] Discord Bot 시작...
echo.
python bot.py

echo.
pause
